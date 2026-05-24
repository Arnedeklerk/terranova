import { useEffect, useState } from "react";
import { invoke, onEvent } from "../bridge";

/**
 * CDSE sign-in panel — drives the OAuth device-code flow.
 *
 * Backed by:
 *   - cdse.status      sync, returns {signed_in: bool, expired: bool}
 *   - cdse.signin      starts a QgsTask, returns {job_id}, emits:
 *       task.cdse.challenge {user_code, verification_uri}
 *       task.progress       {status}
 *       task.complete | task.failed
 *   - cdse.signout     sync, wipes the cached token
 */

interface Status {
  signed_in: boolean;
  expired?: boolean;
}

interface Challenge {
  user_code: string;
  verification_uri: string;
}

export function Cdse() {
  const [status, setStatus] = useState<Status | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const refresh = async () => {
    const r = await invoke<Status>("cdse.status");
    if (r.ok && r.result) setStatus(r.result);
  };
  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!jobId) return;
    return onEvent((payload) => {
      const e = payload as {
        type?: string;
        job_id?: string;
        user_code?: string;
        verification_uri?: string;
        status?: string;
        error?: string;
      };
      if (e.job_id !== jobId) return;
      if (e.type === "task.cdse.challenge") {
        setChallenge({
          user_code: e.user_code ?? "",
          verification_uri: e.verification_uri ?? "",
        });
      } else if (e.type === "task.progress") {
        if (e.status) setStatusText(e.status);
      } else if (e.type === "task.complete") {
        setBusy(false);
        setStatusText("Signed in.");
        setChallenge(null);
        refresh();
      } else if (e.type === "task.failed") {
        setBusy(false);
        setErr(e.error ?? "Sign-in failed.");
        setStatusText("");
      }
    });
  }, [jobId]);

  const startSignin = async () => {
    setErr(null);
    setChallenge(null);
    setStatusText("Requesting device code…");
    setBusy(true);
    const r = await invoke<{ job_id: string }>("cdse.signin");
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "cdse.signin failed");
    }
  };

  const signOut = async () => {
    await invoke("cdse.signout");
    setStatusText("Signed out.");
    refresh();
  };

  return (
    <section className="max-w-2xl">
      <h2 className="text-lg font-semibold mb-2">Sign in to Copernicus Data Space</h2>
      <p className="text-fg-muted text-sm mb-4 leading-relaxed">
        Sign in is required for CDSE downloads (Sentinel-1/2/3, freshest
        ESA-served data).  Authentication happens in your browser via the
        OAuth device-code flow — TerraScope never sees your password.
      </p>

      <div className="bg-bg-1 border border-bg-2 rounded-md p-4 mb-4">
        <div className="text-xs text-fg-muted">Current status</div>
        <div className="text-sm mt-1">
          {status === null ? (
            "Checking…"
          ) : status.signed_in ? (
            status.expired ? (
              <span className="text-warn">
                Signed in, but the token has expired.  Sign in again.
              </span>
            ) : (
              <span className="text-success">Signed in.</span>
            )
          ) : (
            <span className="text-fg-muted">Not signed in.</span>
          )}
        </div>
      </div>

      {challenge && (
        <div className="bg-bg-1 border border-accent rounded-md p-4 mb-4">
          <div className="text-xs text-fg-muted mb-1">Type this code in your browser:</div>
          <div className="text-2xl font-mono tracking-widest mb-3">
            {challenge.user_code}
          </div>
          <a
            href={challenge.verification_uri}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline text-sm"
          >
            Open {challenge.verification_uri} ↗
          </a>
        </div>
      )}

      {statusText && (
        <p className="text-sm text-fg-muted mb-3">{statusText}</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={startSignin}
          disabled={busy}
          className="px-3 py-1.5 bg-accent text-white rounded text-sm disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Start sign-in"}
        </button>
        <button
          onClick={signOut}
          className="px-3 py-1.5 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm"
        >
          Sign out
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}
    </section>
  );
}
