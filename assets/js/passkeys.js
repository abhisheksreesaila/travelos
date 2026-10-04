// Face ID sign-in (F-074): the browser half of gitaway/pages/passkeys.py. Plain JS, no libraries.
// Sign-in page: #si-faceid (and the browser's own passkey suggestions in the email box where it can). Today and /family: #pk-card adds a passkey.
(function () {
  "use strict";
  var supported = !!(window.PublicKeyCredential && navigator.credentials && navigator.credentials.create && navigator.credentials.get);
  var LATER = "ga-faceid-later";
  var KNOWN = "ga-faceid-on";   // F-088: the id of a passkey this phone set up or used for this address. Only presentation: the server still checks every sign-in.

  function bytes(b64) {
    var s = (b64 + "====".slice(b64.length % 4)).replace(/-/g, "+").replace(/_/g, "/"), raw = atob(s), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out.buffer;
  }
  function b64(buf) {
    var a = new Uint8Array(buf), s = "";
    for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function post(path, body) {
    return fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok || j.ok === false) { var err = new Error(j.error || "Face ID did not work. Please try again."); err.unknown = !!j.unknown; throw err; }
        return j;
      });
    });
  }
  function nice(e, google) {
    var more = google ? " Use Continue with Google instead." : "";   // sign-in page only
    if (e && (e.name === "NotAllowedError" || e.name === "AbortError")) return "Face ID was cancelled." + more;
    if (e && e.name === "InvalidStateError") return "Face ID is already on for this phone.";
    return ((e && e.message) || "Face ID did not work.") + more;
  }
  function store(key, value) {
    try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch (e) { return null; }
    return null;
  }
  function forget(key) { try { localStorage.removeItem(key); } catch (e) { /* private mode: nothing to forget */ } }

  function requestOptions(o) {
    o.challenge = bytes(o.challenge);
    (o.allowCredentials || []).forEach(function (c) { c.id = bytes(c.id); });
    return o;
  }
  function creationOptions(o) {
    o.challenge = bytes(o.challenge);
    o.user.id = bytes(o.user.id);
    (o.excludeCredentials || []).forEach(function (c) { c.id = bytes(c.id); });
    return o;
  }
  function answerOf(cred, response) {
    return { id: cred.id, rawId: b64(cred.rawId), type: cred.type, authenticatorAttachment: cred.authenticatorAttachment || undefined,
             clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {}, response: response };
  }

  // ---- sign in ----------------------------------------------------------------------------------------------------------------
  // The button shows only on a phone that has set up or used Face ID for this address; everywhere else Google is the one button. (F-088)
  var button = document.getElementById("si-faceid");
  if (button && supported && store(KNOWN)) {
    var status = document.getElementById("si-faceid-status"), busy = false, conditional = null;
    button.hidden = false;
    var google = true;   // Google is the way in everywhere else
    var failed = function (e) {
      if (e && e.unknown) { forget(KNOWN); button.hidden = true; }   // this address has no such passkey (made before the move?): stop offering Face ID here
      say(nice(e, google), "bad"); busy = false;
    };
    var say = function (text, kind) { status.hidden = !text; status.textContent = text; status.className = "si-note si-faceid-status" + (kind ? " is-" + kind : ""); };
    var finish = function (cred) {
      var r = cred.response;
      return post("/passkeys/auth", {
        credential: answerOf(cred, { clientDataJSON: b64(r.clientDataJSON), authenticatorData: b64(r.authenticatorData), signature: b64(r.signature), userHandle: r.userHandle ? b64(r.userHandle) : null }),
        next: button.getAttribute("data-next") || "/start", intent: button.getAttribute("data-intent") || ""
      }).then(function (j) {
        if (j.passkey) store(KNOWN, j.passkey);
        say("Welcome back, " + j.name, "ok");
        var moment = document.getElementById("si-welcome");
        if (moment) {   // storyboard frame 2: a full-screen welcome for a beat, then Today
          document.getElementById("si-welcome-name").textContent = j.name;
          document.getElementById("si-welcome-device").textContent = /iPhone/.test(navigator.userAgent) ? "iPhone" : "device";
          moment.hidden = false;
        }
        setTimeout(function () { window.location.assign(j.next); }, 1200);
      });
    };
    var ask = function (mediation) {
      return post("/passkeys/auth/options").then(function (o) {
        var opts = { publicKey: requestOptions(o) };
        if (mediation === "conditional") { conditional = new AbortController(); opts.mediation = "conditional"; opts.signal = conditional.signal; }
        return navigator.credentials.get(opts);
      });
    };
    button.addEventListener("click", function () {
      if (busy) return;
      busy = true; say("");
      if (conditional) { conditional.abort(); conditional = null; }
      ask().then(function (cred) { if (cred) return finish(cred); })
        .catch(failed);
    });
    var email = document.getElementById("si-email");
    if (email && PublicKeyCredential.isConditionalMediationAvailable) {
      PublicKeyCredential.isConditionalMediationAvailable().then(function (yes) {
        if (!yes) return;
        email.setAttribute("autocomplete", "username webauthn");
        return ask("conditional").then(function (cred) {
          if (!cred || busy) return;
          busy = true;
          return finish(cred).catch(failed);
        });
      }).catch(function () { /* the person typed or pressed the button instead (the request was cancelled): nothing to say */ });
    }
  }

  // ---- remove a passkey: this phone forgets it when it was the one this phone remembered ---------------------------------------
  Array.prototype.forEach.call(document.querySelectorAll(".pk-item form"), function (f) {
    f.addEventListener("submit", function () {
      var item = f.closest(".pk-item"), mine = store(KNOWN);
      if (mine && item && (item.getAttribute("data-passkey-id") === mine || mine === "1")) forget(KNOWN);
    });
  });

  // ---- add a passkey ---------------------------------------------------------------------------------------------------------
  var card = document.getElementById("pk-card");
  if (card && supported) {
    var where = card.getAttribute("data-where"), add = document.getElementById("pk-add"), later = document.getElementById("pk-later");
    var error = document.getElementById("pk-error"), done = document.getElementById("pk-done");
    var standalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;
    var show = function () { card.hidden = false; add.hidden = false; };
    if (where === "family") {
      show();
    } else if (standalone && !store(LATER)) {   // Today: the first time on a phone in the Home Screen app
      var ok = PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable ? PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable() : Promise.resolve(true);
      ok.then(function (yes) { if (yes) show(); }).catch(function () {});
    }
    var fail = function (text) { error.hidden = !text; error.textContent = text || ""; };
    var working = false;
    add.addEventListener("click", function () {
      if (working) return;
      working = true; fail("");
      post("/passkeys/register/options").then(function (o) { return navigator.credentials.create({ publicKey: creationOptions(o) }); })
        .then(function (cred) {
          var r = cred.response;
          return post("/passkeys/register", { credential: answerOf(cred, {
            clientDataJSON: b64(r.clientDataJSON), attestationObject: b64(r.attestationObject), transports: r.getTransports ? r.getTransports() : [] }) });
        })
        .then(function (j) {
          store(LATER, "1");
          store(KNOWN, (j && j.id) || "1");
          if (where === "family") { window.location.assign("/family#this-phone"); window.location.reload(); return; }
          Array.prototype.forEach.call(card.querySelectorAll(".pk-row, .pk-actions"), function (n) { n.hidden = true; });
          done.hidden = false;
        })
        .catch(function (e) { fail(nice(e)); working = false; });
    });
    if (later) later.addEventListener("click", function () { store(LATER, "1"); card.hidden = true; });
  }
})();
