using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using l99.driver.fanuc;

// All native calls occur synchronously on this one OS thread. Each process is
// dedicated to one machine; stdin accepts endpoints, never function names/code.
internal static class Program
{
    static object? cachedController;
    static string machineType = "";
    static int spindleCount;
    static bool maintenanceSupported;
    static Dictionary<int, short> diagnosticTypes = new();
    static string Text(char[] value) => new string(value ?? Array.Empty<char>()).Trim('\0', ' ');
    internal static string FormatTool(int number, string type) => "T" + number.ToString(
        type.Trim() is "T" or "TT" or "MT" ? "D4" : type.Trim() is "M" or "MM" ? "D2" : "D");
    internal static string FormatProgram(int number) => "O" + number.ToString("D4");
    internal static int FeedOverride(byte raw) => 255 - raw;
    internal static double Scale(int value, short decimals)
    {
        if (decimals < -9 || decimals > 9) throw new InvalidOperationException("Invalid FOCAS decimal scale");
        return value / Math.Pow(10, decimals);
    }
    static string? SpeedUnit(short unit) => unit switch {0 => "mm/min", 1 => "in/min", 2 => "rpm", 3 => "mm/rev", 4 => "in/rev", _ => null};
    static string? LoadUnit(short unit) => unit switch {0 => "%", 1 => "rpm", _ => null};
    static void Require(short code, string function)
    {
        if (code != 0) throw new FocasError(function, code);
    }
    static bool Optional(Func<short> read, string function, Dictionary<string, object> unsupported)
    {
        short code;
        try { code = read(); }
        catch (EntryPointNotFoundException) { unsupported[function] = new {error = "Native read entry point not available"}; return false; }
        if (code is -16 or -17 or -8 or -5 or -10) throw new FocasError(function, code);
        if (code != 0) unsupported[function] = new {code, error = ((Focas.focas_ret)code).ToString()};
        return code == 0;
    }
    // A worker owns one session on its main thread, shared across read sweeps.
    sealed class Session : IDisposable
    {
        readonly Func<string, ushort, int, ushort> open;
        readonly Action<ushort> release;
        (string, ushort, int)? endpoint;
        ushort handle;
        public Session(Func<string, ushort, int, ushort> open, Action<ushort> release)
        { this.open = open; this.release = release; }
        public ushort Ensure(string host, ushort port, int timeout)
        {
            var next = (host, port, timeout);
            if (endpoint == next) return handle;
            Dispose();
            // Record ownership only after allocation succeeds; handle zero is valid.
            handle = open(host, port, timeout);
            endpoint = next;
            return handle;
        }
        public void Dispose()
        {
            if (endpoint is null) return;
            endpoint = null;
            cachedController = null; machineType = ""; spindleCount = 0; maintenanceSupported = false; diagnosticTypes.Clear();
            release(handle);
        }
    }
    static ushort OpenSession(string host, ushort port, int timeout)
    {
        Require(Focas.cnc_allclibhndl3(host, port, timeout, out ushort handle), "cnc_allclibhndl3");
        return handle;
    }
    static void SessionSelfTest()
    {
        int opened = 0; var released = new List<ushort>(); bool fail = false;
        var session = new Session((host, port, timeout) =>
        { if (fail) throw new InvalidOperationException("Test allocation failure"); return (ushort)opened++; }, released.Add);
        void Check(bool value) { if (!value) throw new InvalidOperationException("Session lifecycle self-test failed"); }
        Check(session.Ensure("machine-a", 8193, 3) == 0);
        Check(session.Ensure("machine-a", 8193, 3) == 0 && opened == 1 && released.Count == 0);
        Check(session.Ensure("machine-b", 8193, 3) == 1 && released.SequenceEqual(new ushort[] {0}));
        Check(session.Ensure("machine-b", 8194, 3) == 2);
        Check(session.Ensure("machine-b", 8194, 4) == 3);
        session.Dispose(); // Read failure invalidates ownership before the next sweep.
        Check(session.Ensure("machine-b", 8194, 4) == 4 && opened == 5);
        session.Dispose(); session.Dispose();
        Check(released.SequenceEqual(new ushort[] {0, 1, 2, 3, 4}));
        fail = true;
        try { session.Ensure("machine-a", 8193, 3); throw new Exception("Expected allocation failure"); }
        catch (InvalidOperationException) { }
        session.Dispose(); Check(released.Count == 5);
        fail = false; session.Ensure("machine-a", 8193, 3); session.Dispose();
        Check(opened == 6 && released.Count == 6);
    }
    static object Read(JsonElement endpoint, Session session)
    {
        string host = endpoint.GetProperty("host").GetString()!;
        ushort port = endpoint.GetProperty("port").GetUInt16();
        int timeout = endpoint.GetProperty("timeout").GetInt32();
        if (host.Length is < 1 or > 253 || timeout is < 1 or > 10) throw new InvalidOperationException("Invalid endpoint");
        ushort handle = session.Ensure(host, port, timeout);
        try
        {
            var groups = endpoint.TryGetProperty("groups", out var requested)
                ? requested.EnumerateArray().Select(v => v.GetString()).ToHashSet()
                : new HashSet<string?> {"fast", "status", "slow"};
            if (groups.Any(g => g is not ("fast" or "status" or "slow"))) throw new InvalidOperationException("Invalid read group");
            var system = new Focas.ODBSYS();
            // Controller identity is session-scoped, refreshed only with slow reads.
            if (cachedController is null || groups.Contains("slow"))
            {
                Require(Focas.cnc_sysinfo(handle, system), "cnc_sysinfo");
                string family = Text(system.cnc_type) + (((system.addinfo & 2) != 0) ? "i" : "");
                // Series 15/15i require a different ODBST layout; never call with this buffer.
                if (Text(system.cnc_type) == "15") throw new UnsupportedControllerException("Series 15/15i uses a different status layout and is not supported by this worker");
                machineType = Text(system.mt_type);
                int controllerModel = (system.addinfo >> 8) & 255;
                maintenanceSupported = family == "30i" || (family == "0i" && controllerModel is 4 or 6);
                cachedController = new {series = family, firmware_series = Text(system.series), version = Text(system.version),
                    type = Text(system.mt_type), axes = Text(system.axes), model = "Fanuc " + family, model_code = controllerModel,
                    path_scope = "Default FOCAS path"};
            }
            string group = "fast";
            var signals = new Dictionary<string, object>();
            var unsupported = new Dictionary<string, object>();
            void Add(string name, object? value, string source, string? unit = null, string kind = "sensor", bool available = true) =>
                signals[name] = new {value, source, unit, kind, group, available};
            if (groups.Contains("fast"))
            {
            var state = new Focas.ODBST();
            Require(Focas.cnc_statinfo(handle, state), "cnc_statinfo");
            Add("raw_execution_code", state.run, "cnc_statinfo.run");
            Add("raw_mode_code", state.aut, "cnc_statinfo.aut");
            // Derived labels intentionally describe the raw status, without the
            // upstream controller-specific modal/PMC assumptions.
            Add("execution", state.run switch {0 => "RESET", 1 => "STOPPED", 2 => "FEED_HOLD", 3 => "ACTIVE", 4 => "MSTR", _ => "UNKNOWN"}, "cnc_statinfo.run");
            Add("mode", state.aut switch {0 => "MDI", 1 or 10 => "AUTOMATIC", 2 => "UNSELECTED", 3 => "EDIT", 4 => "HANDLE", 5 => "JOG", 6 => "TEACH_JOG", 7 => "TEACH_HANDLE", 8 => "INCREMENTAL_FEED", 9 => "REFERENCE", 11 => "TEST", _ => "UNKNOWN"}, "cnc_statinfo.aut");
            Add("raw_emergency_code", state.emergency, "cnc_statinfo.emergency");
            // This is an enum, not a boolean: 2 is RESET, 3 is WAIT (FS35i).
            // Only 1 means emergency stop. Do not invent a state for unknown codes.
            if (state.emergency is 0 or 1 or 2 or 3)
                Add("emergency_stop", state.emergency == 1, "cnc_statinfo.emergency", kind: "binary_sensor");
            else unsupported["cnc_statinfo.emergency"] = new {error="Unrecognized emergency status", code=state.emergency};
            Add("raw_alarm_code", state.alarm, "cnc_statinfo.alarm");
            Add("alarm_status", state.alarm switch {0 => "NONE", 1 => "ALARM", 2 => "BATTERY_LOW", 3 => "FAN_ALARM", 4 => "PS_WARNING", 5 => "FSSB_WARNING", 6 => "INSULATION_WARNING", 7 => "ENCODER_WARNING", 8 => "PMC_ALARM", _ => "UNKNOWN"}, "cnc_statinfo.alarm");
            if (state.alarm is >= 0 and <= 8)
                Add("alarm_active", state.alarm is 1 or 3 or 8, "cnc_statinfo.alarm", kind: "binary_sensor");
            else unsupported["cnc_statinfo.alarm"] = new {error="Unrecognized alarm status", code=state.alarm};
            var speed = new Focas.ODBSPEED();
            if (Optional(() => Focas.cnc_rdspeed(handle, -1, speed), "cnc_rdspeed", unsupported))
            {
                if (speed.actf.unit is 0 or 1 or 3 or 4)
                    Add("feed_rate", Scale(speed.actf.data, speed.actf.dec), "cnc_rdspeed.actf", SpeedUnit(speed.actf.unit));
                else unsupported["cnc_rdspeed.actf"] = new {error="Invalid feedrate unit", code=speed.actf.unit};
                if (speed.acts.unit == 2)
                    Add("spindle_rpm", Scale(speed.acts.data, speed.acts.dec), "cnc_rdspeed.acts", "rpm");
                else unsupported["cnc_rdspeed.acts"] = new {error="Invalid spindle speed unit", code=speed.acts.unit};
                Add("raw_feed_unit_code", speed.actf.unit, "cnc_rdspeed.actf.unit");
            }
            // Specified-spindle reads avoid the pinned ABI's four-element array
            // overflowing on controllers supporting eight spindles.
            for (short index = 1; index <= spindleCount; index++)
            {
                var actual = new Focas.ODBACT2();
                if (Optional(() => Focas.cnc_acts2(handle, index, actual), "cnc_acts2."+index, unsupported)
                    && actual.data is {Length: > 0})
                    Add("spindle_"+index+"_rpm", actual.data[0], "cnc_acts2."+index, "rpm");
            }
            if (signals.Keys.Any(name => name != "spindle_rpm" && name.StartsWith("spindle_") && name.EndsWith("_rpm")))
                signals.Remove("spindle_rpm");
            }
            group = "status";
            if (groups.Contains("status"))
            {
            var spindle = new Focas.ODBSPLOAD(); short spindles = 4;
            if (Optional(() => Focas.cnc_rdspmeter(handle, 0, ref spindles, spindle), "cnc_rdspmeter", unsupported))
            {
                spindleCount = Math.Clamp(spindles, (short)0, (short)4);
                for (int index = 1; index <= spindleCount; index++)
                {
                    var data = (Focas.ODBSPLOAD_data)typeof(Focas.ODBSPLOAD).GetField("spload" + index)!.GetValue(spindle)!;
                    if (data.spload.unit == 0)
                        Add("spindle_" + index + "_load", Scale(data.spload.data, data.spload.dec), "cnc_rdspmeter." + index, "%");
                    else unsupported["cnc_rdspmeter."+index] = new {error="Invalid spindle load unit", code=data.spload.unit};
                }
            }
            var axes = new Focas.ODBSVLOAD(); short axisCount = 8;
            if (Optional(() => Focas.cnc_rdsvmeter(handle, ref axisCount, axes), "cnc_rdsvmeter", unsupported))
            {
                for (int index = 1; index <= Math.Clamp(axisCount, (short)0, (short)8); index++)
                {
                    var data = (Focas.LOADELM)typeof(Focas.ODBSVLOAD).GetField("svload" + index)!.GetValue(axes)!;
                    string name = data.name >= 32 && data.name < 127 ? ((char)data.name).ToString() : index.ToString();
                    // Include index in identity to disambiguate duplicate axis names.
                    if (data.unit == 0)
                        Add("axis_" + index + "_" + name + "_load", Scale(data.data, data.dec), "cnc_rdsvmeter." + index, "%");
                    else unsupported["cnc_rdsvmeter."+index] = new {error="Invalid servo load unit", code=data.unit};
                }
            }
            var modal = new Focas.ODBMDL_3();
            if (Optional(() => Focas.cnc_modal(handle, 108, 0, modal), "cnc_modal", unsupported))
            {
                Add("raw_modal_tool_code", modal.aux.aux_data, "cnc_modal.108");
                if (modal.aux.aux_data >= 0) Add("tool_code", FormatTool(modal.aux.aux_data,machineType), "cnc_modal.108");
            }
            // Fixed read-only G12 byte: FANUC active-low feed override input.
            // No software-panel fallback: that field did not track the knobs.
            var overrideData = new Focas.IODBPMC0();
            if (Optional(() => Focas.pmc_rdpmcrng(handle, 0, 0, 12, 12, 9, overrideData), "pmc_rdpmcrng.G12", unsupported))
            {
                if (overrideData.type_a == 0 && overrideData.type_d == 0
                    && overrideData.datano_s == 12 && overrideData.datano_e == 12
                    && overrideData.cdata is {Length: > 0})
                {
                    int percent = FeedOverride(overrideData.cdata[0]);
                    if (percent <= 254)
                    {
                        Add("raw_feed_override_code", overrideData.cdata[0], "pmc_rdpmcrng.G12");
                        Add("feed_override", percent, "pmc_rdpmcrng.G12.active_low", "%");
                    }
                    else unsupported["pmc_rdpmcrng.G12"] = new {error="Reserved feed override value"};
                }
                else unsupported["pmc_rdpmcrng.G12"] = new {error="Invalid PMC G12 response metadata"};
            }
            var alarms = new Focas.ODBALMMSG2(); short alarmCount = 10;
            if (Optional(() => Focas.cnc_rdalmmsg2(handle, -1, ref alarmCount, alarms), "cnc_rdalmmsg2", unsupported))
            {
                var alarmList = new List<object>();
                for (int index = 1; index <= Math.Clamp(alarmCount, (short)0, (short)10); index++)
                {
                    var alarm = (Focas.ODBALMMSG2_data)typeof(Focas.ODBALMMSG2).GetField("msg" + index)!.GetValue(alarms)!;
                    alarmList.Add(new {code = alarm.alm_no, type = alarm.type, axis = alarm.axis, message = alarm.alm_msg[..Math.Min(Math.Clamp(alarm.msg_len,(short)0,(short)64),alarm.alm_msg.Length)].Trim('\0', ' ')});
                }
                Add("alarms", alarmList, "cnc_rdalmmsg2");
                for (short axis = 1; axis <= 8; axis++)
                {
                    bool overtravel = Enumerable.Range(1, Math.Clamp(alarmCount,(short)0,(short)10))
                        .Select(i => (Focas.ODBALMMSG2_data)typeof(Focas.ODBALMMSG2).GetField("msg"+i)!.GetValue(alarms)!)
                        .Any(a => a.type == 4 && a.axis == axis);
                    // Publish axis conditions only for axes actually reported by the load read.
                    if (signals.Keys.Any(k => k.StartsWith("axis_"+axis+"_")))
                    {
                        if (overtravel || alarmCount < 10)
                            Add("axis_"+axis+"_overtravel", overtravel, "cnc_rdalmmsg2.OT", kind:"binary_sensor");
                        else unsupported["cnc_rdalmmsg2.OT."+axis] = new {error="Full alarm buffer cannot confirm absence of overtravel"};
                    }
                }
                Add("raw_alarm_buffer_full", alarmCount == 10, "cnc_rdalmmsg2.count", kind: "binary_sensor");
            }
            var messages = new Focas.OPMSG();
            if (Optional(() => Focas.cnc_rdopmsg(handle, 0, 262, messages), "cnc_rdopmsg", unsupported))
            {
                var msg = messages.msg1;
                if (msg.datano == -1) Add("machine_message", "", "cnc_rdopmsg.msg1");
                else if (msg.type == 0 && msg.char_num is > 0 and <= 256)
                    Add("machine_message", msg.data[..Math.Min(msg.char_num,msg.data.Length)].Trim('\0',' '), "cnc_rdopmsg.msg1");
                else unsupported["cnc_rdopmsg"] = new {error="Invalid operator message metadata"};
            }
            }
            group = "slow";
            if (groups.Contains("slow"))
            {
            var program = new Focas.ODBPRO();
            if (Optional(() => Focas.cnc_rdprgnum(handle, program), "cnc_rdprgnum", unsupported))
            {
                if (program.data < 0 || program.mdata < 0)
                    unsupported["cnc_rdprgnum"] = new {error="Invalid program number in four-digit ABI"};
                else
                {
                Add("program_number", FormatProgram(program.data), "cnc_rdprgnum.data");
                Add("main_program_number", FormatProgram(program.mdata), "cnc_rdprgnum.mdata");
                int number = program.data; short count = 1; var directory = new Focas.PRGDIR3();
                if (Optional(() => Focas.cnc_rdprogdir3(handle, 2, ref number, ref count, directory), "cnc_rdprogdir3", unsupported) && count > 0 && directory.dir1.number == program.data)
                    Add("program_comment", directory.dir1.comment.Trim('\0', ' '), "cnc_rdprogdir3.comment");
                }
            }

                // Fixed maintenance mappings only. Verify existence and layout with
                // the controller before reading; do not manufacture empty entities.
                if (maintenanceSupported)
                {
                    void Diagnostic(short number, short axis, string name, int expectedType, string unit, int minimum, int maximum, bool spindleDiagnostic=false)
                    {
                        string source = "cnc_diagnoss."+number+"."+axis;
                        if (!diagnosticTypes.TryGetValue(number, out short attribute))
                        {
                            var info = new Focas.ODBDIAGIF();
                            if (!Optional(() => Focas.cnc_rddiaginfo(handle, number, 1, info), "cnc_rddiaginfo."+number, unsupported)) return;
                            if (info.info_no != 1 || info.info.info1.diag_no != number) { unsupported[source] = new {error="Diagnostic is not present"}; return; }
                            attribute = info.info.info1.diag_type; diagnosticTypes[number] = attribute;
                        }
                        if ((attribute & 3) != expectedType || (attribute & (8|4096)) != 0
                            || (spindleDiagnostic ? (attribute & 256) == 0 : (attribute & 4) == 0 || (attribute & 256) != 0))
                        { unsupported[source] = new {error="Diagnostic type does not match maintenance mapping"}; return; }
                        var data = new Focas.ODBDGN_1();
                        short length = (short)(4 + (expectedType == 1 ? 1 : expectedType == 2 ? 2 : 4));
                        if (!Optional(() => Focas.cnc_diagnoss(handle, number, axis, length, data), source, unsupported)) return;
                        if (data.datano != number || (data.type & 255) != axis)
                        { unsupported[source] = new {error="Diagnostic response number/axis does not match request"}; return; }
                        bool signed = (attribute & 128) != 0;
                        long value = expectedType == 1 ? (signed ? (sbyte)data.cdata : data.cdata)
                            : expectedType == 2 ? (signed ? data.idata : (ushort)data.idata)
                            : signed ? data.ldata : (long)(uint)data.ldata;
                        if (value < minimum || value > maximum) { unsupported[source] = new {error="Diagnostic value outside validated range"}; return; }
                        if (unit == "°C" && value == 0)
                        {
                            unsupported[source] = new {error="Zero temperature is treated as unavailable"};
                            Add(name, null, source, unit, available:false);
                            return;
                        }
                        Add(name, value, source, unit);
                    }
                    int count = int.TryParse(Text(system.axes), out int n) ? Math.Clamp(n,0,8) : 0;
                    for (short axis=1; axis<=count; axis++)
                    {
                        Diagnostic(308,axis,"axis_"+axis+"_motor_temperature",1,"°C",0,255);
                        Diagnostic(309,axis,"axis_"+axis+"_encoder_temperature",1,"°C",0,255);
                        Diagnostic(4901,axis,"axis_"+axis+"_power",3,"W",-99999999,99999999);
                    }
                    for (short spindle=1; spindle<=spindleCount; spindle++)
                    {
                        Diagnostic(403,spindle,"spindle_"+spindle+"_motor_temperature",1,"°C",0,255,spindleDiagnostic:true);
                        Diagnostic(4902,spindle,"spindle_"+spindle+"_power",3,"W",-99999999,99999999,spindleDiagnostic:true);
                    }
                }
            }
            if (groups.Contains("slow") && !maintenanceSupported)
                unsupported["cnc_diagnoss.mapping"] = new {error="Maintenance mappings require 0i-D/F or 30i controller identification"};
            return new {controller = cachedController, signals, unsupported, simulation = false};
        }
        catch { session.Dispose(); throw; }
    }
    static int Main(string[] args)
    {
        if (args.SequenceEqual(new[] {"--self-test"}))
        {
            SessionSelfTest();
            if (Scale(450, 2) != 4.5 || SpeedUnit(1) != "in/min" || LoadUnit(0) != "%") return 1;
            if (FormatTool(303,"T") != "T0303" || FormatTool(303,"MT") != "T0303"
                || FormatTool(303,"TT") != "T0303" || FormatTool(7,"M") != "T07"
                || FormatTool(7,"MM") != "T07" || FormatTool(123456,"T") != "T123456"
                || FormatProgram(53) != "O0053" || FormatProgram(123456) != "O123456") return 1;
            foreach (var pair in new (byte raw,int percent)[] {(255,0),(205,50),(155,100),(135,120),(105,150),(55,200)})
                if (FeedOverride(pair.raw) != pair.percent) return 1;
            var imports = typeof(Focas).GetMethods().Where(m => m.IsDefined(typeof(DllImportAttribute))).Select(m => m.Name).Distinct().Order().ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {mapping_tests = "passed", session_tests = "passed", imports}));
            return 0;
        }
        bool started = false;
        var session = new Session(OpenSession, handle => { Focas.cnc_freelibhndl(handle); });
        try
        {
            string libraryPath = Environment.GetEnvironmentVariable("FOCAS_LIBRARY_PATH")
                ?? "/opt/monitor/native/libfwlib32-linux-x64.so.1.0.5";
            NativeLibrary.SetDllImportResolver(typeof(Focas).Assembly, (name, assembly, path) =>
                name == FocasLibConstants.FileName ? NativeLibrary.Load(libraryPath) : IntPtr.Zero);
            if (args.SequenceEqual(new[] {"--native-self-test"}))
            {
                // Load and resolve only; never allocate a CNC session or connect.
                IntPtr library = NativeLibrary.Load(libraryPath);
                try
                {
                    var imports = typeof(Focas).GetMethods().Where(m => m.IsDefined(typeof(DllImportAttribute)))
                        .Select(m => m.GetCustomAttribute<DllImportAttribute>()!.EntryPoint ?? m.Name).Distinct().ToArray();
                    foreach (string symbol in imports) NativeLibrary.GetExport(library, symbol);
                    Console.WriteLine(JsonSerializer.Serialize(new {native_load = "passed", exports = imports.Length, cnc_connections = 0}));
                }
                finally { NativeLibrary.Free(library); }
                return 0;
            }
            Require(Focas.cnc_startupprocess(0, "/data/focas.log"), "cnc_startupprocess"); started = true;
            string? line;
            while ((line = Console.ReadLine()) != null)
            {
                try { using var request = JsonDocument.Parse(line); Console.WriteLine(JsonSerializer.Serialize(Read(request.RootElement, session))); }
                catch (UnsupportedControllerException error) { Console.WriteLine(JsonSerializer.Serialize(new {error = error.Message})); }
                catch (FocasError error) { Console.WriteLine(JsonSerializer.Serialize(new {error = error.Message, code = error.Code})); }
                catch (Exception) { Console.WriteLine("{\"error\":\"Invalid native data or unavailable FOCAS read entry point\"}"); }
            }
        }
        catch (Exception) { Console.WriteLine("{\"error\":\"FOCAS native library failed to initialize; verify Linux amd64 dependencies and license\"}"); return 1; }
        finally { try { session.Dispose(); } finally { if (started) Focas.cnc_exitprocess(); } }
        return 0;
    }
    sealed class UnsupportedControllerException(string message) : Exception(message);
    sealed class FocasError(string function, short code) : Exception($"{function}: {((Focas.focas_ret)code)} ({code})")
    {
        public short Code { get; } = code;
    }
}
