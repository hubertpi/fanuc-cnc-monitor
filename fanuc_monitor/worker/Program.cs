using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using l99.driver.fanuc;

// All native calls occur synchronously on this one OS thread. Each process is
// dedicated to one machine; stdin accepts endpoints, never function names/code.
internal static class Program
{
    static string Text(char[] value) => new string(value ?? Array.Empty<char>()).Trim('\0', ' ');
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
    static object Read(JsonElement endpoint)
    {
        string host = endpoint.GetProperty("host").GetString()!;
        ushort port = endpoint.GetProperty("port").GetUInt16();
        int timeout = endpoint.GetProperty("timeout").GetInt32();
        if (host.Length is < 1 or > 253 || timeout is < 1 or > 10) throw new InvalidOperationException("Invalid endpoint");
        Require(Focas.cnc_allclibhndl3(host, port, timeout, out ushort handle), "cnc_allclibhndl3");
        try
        {
            var system = new Focas.ODBSYS();
            Require(Focas.cnc_sysinfo(handle, system), "cnc_sysinfo");
            var state = new Focas.ODBST();
            Require(Focas.cnc_statinfo(handle, state), "cnc_statinfo");
            var signals = new Dictionary<string, object>();
            var unsupported = new Dictionary<string, object>();
            void Add(string name, object value, string source, string? unit = null, string kind = "sensor") =>
                signals[name] = new {value, source, unit, kind};
            Add("raw_execution_code", state.run, "cnc_statinfo.run");
            Add("raw_mode_code", state.aut, "cnc_statinfo.aut");
            // Derived labels intentionally describe the raw status, without the
            // upstream controller-specific modal/PMC assumptions.
            Add("execution", state.run switch {0 => "READY", 1 => "STOPPED", 2 => "FEED_HOLD", 3 => "ACTIVE", _ => "UNKNOWN"}, "cnc_statinfo.run");
            Add("mode", state.aut switch {0 => "MDI", 1 or 10 => "AUTOMATIC", 3 => "EDIT", _ => "MANUAL_OR_UNKNOWN"}, "cnc_statinfo.aut");
            Add("emergency_stop", state.emergency != 0, "cnc_statinfo.emergency", kind: "binary_sensor");
            Add("alarm_active", state.alarm != 0, "cnc_statinfo.alarm", kind: "binary_sensor");
            var speed = new Focas.ODBSPEED();
            if (Optional(() => Focas.cnc_rdspeed(handle, -1, speed), "cnc_rdspeed", unsupported))
            {
                Add("feed_rate", Scale(speed.actf.data, speed.actf.dec), "cnc_rdspeed.actf", SpeedUnit(speed.actf.unit));
                Add("spindle_rpm", Scale(speed.acts.data, speed.acts.dec), "cnc_rdspeed.acts", SpeedUnit(speed.acts.unit));
                Add("raw_feed_unit_code", speed.actf.unit, "cnc_rdspeed.actf.unit");
            }
            var spindle = new Focas.ODBSPLOAD(); short spindles = 4;
            if (Optional(() => Focas.cnc_rdspmeter(handle, 0, ref spindles, spindle), "cnc_rdspmeter", unsupported))
            {
                for (int index = 1; index <= Math.Clamp(spindles, (short)0, (short)4); index++)
                {
                    var data = (Focas.ODBSPLOAD_data)typeof(Focas.ODBSPLOAD).GetField("spload" + index)!.GetValue(spindle)!;
                    Add("spindle_" + index + "_load", Scale(data.spload.data, data.spload.dec), "cnc_rdspmeter." + index, LoadUnit(data.spload.unit));
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
                    Add("axis_" + index + "_" + name + "_load", Scale(data.data, data.dec), "cnc_rdsvmeter." + index, LoadUnit(data.unit));
                }
            }
            var program = new Focas.ODBPRO();
            if (Optional(() => Focas.cnc_rdprgnum(handle, program), "cnc_rdprgnum", unsupported))
            {
                Add("program_number", program.data, "cnc_rdprgnum.data");
                Add("main_program_number", program.mdata, "cnc_rdprgnum.mdata");
                int number = program.data; short count = 1; var directory = new Focas.PRGDIR3();
                if (Optional(() => Focas.cnc_rdprogdir3(handle, 2, ref number, ref count, directory), "cnc_rdprogdir3", unsupported) && count > 0 && directory.dir1.number == program.data)
                    Add("program_comment", directory.dir1.comment.Trim('\0', ' '), "cnc_rdprogdir3.comment");
            }
            var modal = new Focas.ODBMDL_3();
            if (Optional(() => Focas.cnc_modal(handle, 108, 0, modal), "cnc_modal", unsupported))
                Add("raw_modal_tool_code", modal.aux.aux_data, "cnc_modal.108");
            var panel = new Focas.IODBSGNL();
            if (Optional(() => Focas.cnc_rdopnlsgnl(handle, 0, panel), "cnc_rdopnlsgnl", unsupported))
                Add("raw_feed_override_code", panel.feed_ovrd, "cnc_rdopnlsgnl.feed_ovrd");
            var alarms = new Focas.ODBALMMSG2(); short alarmCount = 10;
            if (Optional(() => Focas.cnc_rdalmmsg2(handle, -1, ref alarmCount, alarms), "cnc_rdalmmsg2", unsupported))
            {
                var alarmList = new List<object>();
                for (int index = 1; index <= Math.Clamp(alarmCount, (short)0, (short)10); index++)
                {
                    var alarm = (Focas.ODBALMMSG2_data)typeof(Focas.ODBALMMSG2).GetField("msg" + index)!.GetValue(alarms)!;
                    alarmList.Add(new {code = alarm.alm_no, type = alarm.type, axis = alarm.axis, message = alarm.alm_msg.Trim('\0', ' ')});
                }
                Add("alarms", alarmList, "cnc_rdalmmsg2");
                Add("raw_alarm_buffer_full", alarmCount == 10, "cnc_rdalmmsg2.count", kind: "binary_sensor");
            }
            var messages = new Focas.OPMSG();
            if (Optional(() => Focas.cnc_rdopmsg(handle, 0, 262, messages), "cnc_rdopmsg", unsupported))
                Add("machine_message", messages.msg1.data.Trim('\0', ' '), "cnc_rdopmsg.msg1");
            string family = Text(system.cnc_type) + (((system.addinfo & 2) != 0) ? "i" : "");
            return new {controller = new {series = family, firmware_series = Text(system.series), version = Text(system.version),
                type = Text(system.mt_type), axes = Text(system.axes), model = "Fanuc " + family,
                path_scope = "Default FOCAS path only; multi-path qualification pending"}, signals, unsupported, simulation = false};
        }
        finally { Focas.cnc_freelibhndl(handle); }
    }
    static int Main(string[] args)
    {
        if (args.SequenceEqual(new[] {"--self-test"}))
        {
            if (Scale(450, 2) != 4.5 || SpeedUnit(1) != "in/min" || LoadUnit(0) != "%") return 1;
            var imports = typeof(Focas).GetMethods().Where(m => m.IsDefined(typeof(DllImportAttribute))).Select(m => m.Name).Distinct().Order().ToArray();
            Console.WriteLine(JsonSerializer.Serialize(new {mapping_tests = "passed", imports}));
            return 0;
        }
        bool started = false;
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
                try { using var request = JsonDocument.Parse(line); Console.WriteLine(JsonSerializer.Serialize(Read(request.RootElement))); }
                catch (FocasError error) { Console.WriteLine(JsonSerializer.Serialize(new {error = error.Message, code = error.Code})); }
                catch (Exception) { Console.WriteLine("{\"error\":\"Invalid native data or unavailable FOCAS read entry point\"}"); }
            }
        }
        catch (Exception) { Console.WriteLine("{\"error\":\"FOCAS native library failed to initialize; verify Linux amd64 dependencies and license\"}"); return 1; }
        finally { if (started) Focas.cnc_exitprocess(); }
        return 0;
    }
    sealed class FocasError(string function, short code) : Exception($"{function}: {((Focas.focas_ret)code)} ({code})")
    {
        public short Code { get; } = code;
    }
}
