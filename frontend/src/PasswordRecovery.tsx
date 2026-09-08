import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ArrowLeft, CheckCircle2, Copy, KeyRound, Mail, X } from "lucide-react";

export function PasswordRecovery({ token, apiUrl, onBack }: { token: string; apiUrl: string; onBack: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setError("");
    if (token && data.get("password") !== data.get("confirmation")) {
      setError("Les deux mots de passe doivent être identiques."); return;
    }
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl}/auth/password-reset/${token ? "confirm" : "request"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(token ? { token, password: data.get("password") } : { email: data.get("email") }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Vérifiez les informations saisies.");
      if (typeof result.message !== "string") throw new Error("Réponse du serveur inattendue. Réessayez.");
      setMessage(result.message); form.reset();
    } catch (e) { setError(e instanceof Error ? e.message : "Réinitialisation impossible."); }
    finally { setBusy(false); }
  }
  return <div className="password-recovery">
    <h2>{token ? "Choisir un nouveau mot de passe" : "Mot de passe oublié"}</h2>
    <p>{token ? "Saisissez un mot de passe de 12 à 128 caractères." : "Indiquez l’adresse e-mail de votre compte InfoBridge."}</p>
    {error && <p className="form-error" role="alert">{error}</p>}
    {message ? <p className="app-message" role="status"><CheckCircle2 size={18} /> {message}</p> : <form className="login-form" onSubmit={submit}>
      {token ? <>
        <label><span>Nouveau mot de passe</span><div className="input-control"><KeyRound size={18} /><input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required autoFocus /></div></label>
        <label><span>Confirmer le nouveau mot de passe</span><div className="input-control"><KeyRound size={18} /><input name="confirmation" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></div></label>
      </> : <label><span>Adresse e-mail</span><div className="input-control"><Mail size={18} /><input name="email" type="email" autoComplete="email" required autoFocus /></div></label>}
      <button className="primary-button login-submit" disabled={busy}><KeyRound size={18} />{busy ? "Traitement…" : token ? "Enregistrer le mot de passe" : "Recevoir un lien"}</button>
    </form>}
    <button className="ghost-button recovery-back" type="button" disabled={busy} onClick={onBack}><ArrowLeft size={16} />Retour à la connexion</button>
  </div>;
}

export function ResetLinkDialog({ data, onClose }: { data: { name: string; reset_url: string; expires_at: string }; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} className="reset-link-dialog" aria-labelledby="reset-link-title" onCancel={onClose}>
    <h2 id="reset-link-title">Réinitialiser le mot de passe</h2><p><strong>{data.name}</strong></p>
    <p>Transmettez ce lien uniquement à la personne concernée. Il est utilisable une seule fois, jusqu’au {new Date(data.expires_at).toLocaleString("fr-FR")}.</p>
    <label>Lien de réinitialisation<input readOnly value={data.reset_url} onFocus={e => e.target.select()} /></label>
    {error && <p role="alert">{error}</p>}
    <div className="row-actions"><button className="secondary-button" onClick={async () => { try { await navigator.clipboard.writeText(data.reset_url); setCopied(true); } catch { setError("Sélectionnez le lien et copiez-le manuellement."); } }}><Copy size={16} />{copied ? "Copié" : "Copier le lien"}</button><button className="ghost-button" onClick={onClose}><X size={16} />Fermer</button></div>
  </dialog>;
}
