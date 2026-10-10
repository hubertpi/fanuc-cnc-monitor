"use strict";
const $ = id => document.getElementById(id);
let status = null, editing = null, removing = null, detailId = null, testToken = "", originalEndpoint = "";
const endpoint = () => ({host: $("host").value.trim(), port: Number($("port").value), timeout: Number($("timeout").value)});
const endpointKey = value => JSON.stringify([value.host, value.port, value.timeout]);
const text = (tag, value, className) => { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; };
const when = value => value ? new Date(value).toLocaleString() : "No successful read";
async function api(path, method = "GET", body) {
  const response = await fetch(`api/${path}`, {method, headers: {"Content-Type": "application/json", "X-Monitor-CSRF": status?.csrf || "", "X-Connection-Test": testToken}, body: body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) { const error = result.detail || result.error || "Request failed"; throw new Error(Array.isArray(error) ? error.map(e => `${e.loc.at(-1)}: ${e.msg}`).join("; ") : error); }
  return result;
}
function openEditor(machine = null) {
  editing = machine; testToken = ""; originalEndpoint = machine ? endpointKey(machine) : "";
  $("editor-title").textContent = machine ? "Edit machine" : "Add machine";
  for (const [field, fallback] of Object.entries({host: "", port:8193, timeout:3, name:"", interval:1})) $(field).value = machine?.[field] ?? fallback;
  $("enabled").checked = machine?.enabled ?? true;
  $("test-result").className = "test-result";
  $("test-result").textContent = machine ? "The saved address is already configured. Test again if you change it." : "Enter an address and test to detect controller information.";
  $("form-error").textContent = ""; $("save").disabled = !machine; $("editor").showModal();
}
for (const field of ["host", "port", "timeout"]) $(field).addEventListener("input", () => {testToken = ""; $("save").disabled = endpointKey(endpoint()) !== originalEndpoint; $("test-result").textContent = "Connection settings changed. Test this address before saving."; $("test-result").className = "test-result";});
$("test").onclick = async () => {
  if (!$("host").reportValidity() || !$("port").reportValidity() || !$("timeout").reportValidity()) return;
  const tested = endpointKey(endpoint()); $("test").disabled = true; $("save").disabled = true;
  $("test-result").className = "test-result"; $("test-result").textContent = "Testing connection and reading controller information…";
  try {
    const result = await api("test", "POST", endpoint());
    if (tested !== endpointKey(endpoint())) throw new Error("Address changed during the test. Please test again.");
    testToken = result.test_token;
    const c = result.controller;
    $("test-result").textContent = `${result.simulation ? "SIMULATION — no CNC connection was made" : "FOCAS read succeeded"}\nController: ${c.model || c.series || "Identification incomplete"} · Version ${c.version || "unknown"} · ${c.axes ?? "unknown"} axes\n${result.values_collected} collected values. Name suggested below; you can edit it.`;
    $("test-result").className = "test-result ok";
    if (!editing || !$("name").value.trim()) $("name").value = result.suggested_name;
    $("save").disabled = false;
  } catch (error) { testToken = ""; $("test-result").textContent = error.message; $("test-result").className = "test-result fail"; }
  finally { $("test").disabled = false; }
};
$("machine-form").onsubmit = async event => {
  event.preventDefault(); $("save").disabled = true; $("form-error").textContent = "";
  const value = {...endpoint(), name:$("name").value.trim(), interval:Number($("interval").value), enabled:$("enabled").checked};
  if (editing) value.revision = editing.revision;
  try {await api(editing ? `machines/${editing.id}` : "machines", editing ? "PUT" : "POST", value); $("editor").close(); await refresh();}
  catch (error) {$("form-error").textContent = error.message;}
  finally {$("save").disabled = false;}
};
function showDetails(machine) {
  detailId = machine.id; $("details-title").textContent = machine.name;
  const body = $("details-body"); body.replaceChildren();
  body.append(text("div", `${machine.host}:${machine.port}\nConnection: ${machine.online ? "Online" : "Offline"} · Collector: ${status.mode}\nLast attempted read: ${when(machine.last_attempt)}\nLast successful data read: ${when(machine.last_success)}\nReconnect attempts: ${machine.reconnect_attempts}\nError: ${machine.error || "None"}${machine.error_code != null ? ` (${machine.error_code})` : ""}`, "diagnostic-summary"));
  body.append(text("h3", "Collected observations", "details-signals"));
  const wrap = text("div", "", "table-scroll"), table = document.createElement("table"), head = document.createElement("tr");
  for (const label of ["Signal / source", "Value", "Last read", "MQTT"]) head.append(text("th", label)); table.append(head);
  for (const [name, signal] of Object.entries(machine.signals)) {
    const row = document.createElement("tr"), source = text("td", name); source.append(text("small", signal.source)); row.append(source, text("td", `${typeof signal.value === "object" ? JSON.stringify(signal.value) : signal.value} ${signal.unit || ""}`), text("td", when(signal.last_read)), text("td", signal.published && signal.discovery_published ? "Acknowledged" : "Pending")); table.append(row);
  }
  wrap.append(table); body.append(wrap);
  if (Object.keys(machine.unsupported || {}).length) body.append(text("p", "Unsupported reads: " + JSON.stringify(machine.unsupported)));
  if (!$("details").open) $("details").showModal();
}
function render() {
  const machines = status.machines;
  $("total").textContent = machines.length; $("connected").textContent = machines.filter(m => m.online).length;
  $("disconnected").textContent = machines.filter(m => !m.online).length;
  $("mqtt").textContent = status.mqtt_connected ? "Connected" : "Disconnected";
  $("mode-banner").textContent = status.mode === "simulation" ? "SIMULATION MODE · All machine data is simulated. No CNC equipment is contacted." : "FOCAS MODE · Authorized read-only hardware testing. Controller compatibility remains subject to validation.";
  $("mode-banner").className = status.mode === "simulation" ? "banner" : "banner live";
  const error = status.startup_error || status.mqtt_error; $("notice").hidden = !error; $("notice").textContent = error || "";
  $("empty").hidden = machines.length !== 0; $("machines").replaceChildren();
  for (const machine of machines) {
    const card = text("article", "", "machine"), top = text("div", "", "machine-top"), title = document.createElement("div");
    title.append(text("h3", machine.name), text("span", machine.controller.model || "Controller identification pending", "model"));
    top.append(title, text("span", machine.online ? "● ONLINE" : machine.enabled ? "● OFFLINE" : "● DISABLED", "badge" + (machine.online ? "" : " off"))); card.append(top);
    const data = document.createElement("dl");
    for (const [label,value] of [["FOCAS ENDPOINT",`${machine.host}:${machine.port}`],["READ INTERVAL",`${machine.interval} seconds`],["LAST SUCCESSFUL READ",when(machine.last_success)],["COLLECTED VALUES",Object.keys(machine.signals).length]]) {const item = document.createElement("div"); item.append(text("dt",label), text("dd",value)); data.append(item);} card.append(data);
    if (machine.error) card.append(text("p", machine.error, "error"));
    const actions = text("div", "", "machine-actions");
    for (const [label,fn,cls] of [["Details",()=>showDetails(machine),""],["Edit",()=>openEditor(machine),""],["Remove",()=>{removing=machine; $("remove-name").textContent=machine.name; $("remove-error").textContent=""; $("removal").showModal();},"remove"]]) {const button=text("button",label,cls);button.onclick=fn;actions.append(button);} card.append(actions); $("machines").append(card);
  }
  if ($("details").open) {const machine=machines.find(m=>m.id===detailId); if(machine)showDetails(machine); else $("details").close();}
}
async function refresh() {try {status=await api("status"); render(); $("refresh-state").textContent="Updated " + new Date().toLocaleTimeString();} catch(error) {$("notice").hidden=false;$("notice").textContent="Cannot reach collector: " + error.message;}}
$("add").onclick=()=>openEditor(); $("empty-add").onclick=()=>openEditor();
for (const id of ["close-editor","cancel-editor"]) $(id).onclick=()=>$("editor").close();
$("close-details").onclick=()=>$("details").close(); $("cancel-remove").onclick=()=>$("removal").close();
$("confirm-remove").onclick=async()=>{ $("confirm-remove").disabled=true;try{await api(`machines/${removing.id}`,"DELETE");$("removal").close();await refresh();}catch(error){$("remove-error").textContent=error.message;}finally{$("confirm-remove").disabled=false;}};
$("export").onclick=async()=>{try{const blob=new Blob([JSON.stringify(await api("diagnostics"),null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download="fanuc-diagnostics.json";link.click();URL.revokeObjectURL(url);}catch(error){$("notice").hidden=false;$("notice").textContent=error.message;}};
refresh(); setInterval(refresh,2000);
