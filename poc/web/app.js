"use strict";

const logEl = document.getElementById("log");
function log(msg) {
  logEl.textContent += new Date().toISOString().slice(11, 23) + " " + msg + "\n";
}

// Report any CSP violation so the PoC can document what AutoScript needs.
document.addEventListener("securitypolicyviolation", (e) => {
  log("CSP VIOLATION: " + e.violatedDirective + " blocked " + (e.blockedURI || "inline"));
});

async function loadConstituencies() {
  const r = await fetch("/api/circunscripciones");
  const list = await r.json();
  const sel = document.getElementById("circ");
  for (const c of list) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    sel.appendChild(o);
  }
  const d = await (await fetch("/api/defaults")).json();
  for (const [k, v] of Object.entries(d)) {
    const field = document.getElementById("f").elements[k];
    if (field) field.value = v;
  }
}

function sign(xmlB64, params) {
  return new Promise((resolve, reject) => {
    AutoScript.sign(xmlB64, "SHA256withRSA", "XAdES", params,
      (signedB64, certB64) => resolve({ signedB64, certB64 }),
      (type, msg) => reject(new Error(type + ": " + msg)));
  });
}

document.getElementById("f").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const form = new FormData(ev.target);
  const body = Object.fromEntries(form.entries());
  const variant = body.variant;
  delete body.variant;
  try {
    log("POST /api/aval variant " + variant);
    const r = await fetch("/api/aval?variant=" + variant, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const created = await r.json();
    if (!r.ok) { log("server rejected: " + JSON.stringify(created)); return; }
    log("params:\n" + created.params);
    log("calling AutoFirma (confirm in its window)...");
    const { signedB64 } = await sign(created.xml_b64, created.params);
    log("signed XML received from AutoFirma, " + signedB64.length + " b64 chars");
    const v = await fetch("/api/aval/" + created.id + "/signed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ xml_b64: signedB64 }),
    });
    log("server report:\n" + JSON.stringify(await v.json(), null, 2));
  } catch (e) {
    log("ERROR: " + e.message);
  }
});

try {
  AutoScript.cargarAppAfirma();
  log("AutoScript " + AutoScript.VERSION + " loaded; UA: " + navigator.userAgent);
} catch (e) {
  log("AutoScript init error: " + e.message);
}
loadConstituencies();
