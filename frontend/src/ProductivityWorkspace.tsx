import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Archive, CheckCircle2, ClipboardCheck, FileSearch, MessageSquareText, Plus, RefreshCw, Save, Search, Send, Settings, ShieldCheck, Users, X } from "lucide-react";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Case = { id: string; reference: string; subject: string; status: string; request_type?: string; assigned_to: string | null; sender_institution_id: string; receiver_institution_id: string };
type User = { id: string; institution_id: string; role: string };
type Policy = { id: string; name: string; institution_id: string; request_type: string; classification: string | null; required_purposes: string[]; validation_roles: string[]; active: boolean };
type Workspace = {
  case: Case;
  checklist: { request_type: string; complete: boolean; configured: boolean; items: { purpose: string; present: boolean }[] };
  comments: { id: string; author: string; body: string; visibility: string; created_at: string }[];
  members: { id: string; name: string; role: string }[];
  timeline: { id: string; action: string; comment: string | null; created_at: string }[];
  validation_steps: string[]; validation_progress: { user_id: string; role: string; at: string; comment: string }[]; is_operator: boolean;
  delegate_candidates: { id: string; name: string }[];
  delegations: { id: string; delegate_name: string; delegate_id: string; starts_at: string; ends_at: string; revoked_at: string | null }[];
};
type Summary = { overview: string; proposal: string; coverage: string; sources: { attachment_id: string; file_name: string; excerpt: string; coverage: string }[] };
type SearchResult = { results: { case_id: string; reference: string; file_name: string; excerpt: string; coverage: string }[]; warnings: { file_name: string; coverage: string }[]; next_offset: number | null; scanned: number };
type Block = { id: string; reference: string; subject: string; status: string; days_waiting: number; reasons: string[] };
const date = (value: string) => new Date(value).toLocaleString("fr-FR");
const role = (value: string) => ({ VALIDATOR: "Validateur", INSTITUTION_ADMIN: "Admin institution", SYSTEM_ADMIN: "Admin système", AGENT: "Agent" }[value] ?? value);

export function ProductivityWorkspace({ api, cases, currentUser, institutions, initialCaseId, onRefresh }: {
  api: Api; cases: Case[]; currentUser: User; institutions: { id: string; name: string }[];
  initialCaseId: string; onRefresh: () => Promise<void>;
}) {
  const apiRef = useRef(api); apiRef.current = api;
  const [caseId, setCaseId] = useState(initialCaseId || cases[0]?.id || "");
  const [tab, setTab] = useState("case");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [proposal, setProposal] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [query, setQuery] = useState("");
  const [searchedQuery, setSearchedQuery] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);
  const [policyVersion, setPolicyVersion] = useState(0);
  const requestGeneration = useRef(0);
  const selected = workspace?.case.id === caseId ? workspace.case : cases.find(item => item.id === caseId);
  const admin = ["SYSTEM_ADMIN", "INSTITUTION_ADMIN"].includes(currentUser.role);
  const writer = ["SYSTEM_ADMIN", "INSTITUTION_ADMIN", "AGENT", "VALIDATOR"].includes(currentUser.role);
  const sender = currentUser.role === "SYSTEM_ADMIN" || selected?.sender_institution_id === currentUser.institution_id;
  const receiver = currentUser.role === "SYSTEM_ADMIN" || selected?.receiver_institution_id === currentUser.institution_id;
  const path = `/productivity/cases/${caseId}`;

  useEffect(() => {
    let live = true;
    Promise.all([apiRef.current<Policy[]>("/productivity/policies"), apiRef.current<Block[]>("/productivity/bottlenecks")])
      .then(([p, b]) => { if (live) { setPolicies(p); setBlocks(b); } }).catch(e => { if (live) setError(String(e.message)); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    const generation = ++requestGeneration.current;
    setWorkspace(null); setSummary(null); setProposal(""); setError(""); setMessage("");
    if (!caseId) return;
    setLoading(true);
    apiRef.current<Workspace>(`/productivity/cases/${caseId}/workspace`).then(data => {
      if (generation === requestGeneration.current) setWorkspace(data);
    }).catch(e => { if (generation === requestGeneration.current) setError(e.message); })
      .finally(() => { if (generation === requestGeneration.current) setLoading(false); });
    return () => { requestGeneration.current++; };
  }, [caseId]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Action impossible"); }
    finally { setBusy(false); }
  }
  async function reloadCase() {
    setWorkspace(await apiRef.current<Workspace>(`${path}/workspace`));
    await onRefresh();
  }
  const post = (url: string, body: unknown, method = "POST") => apiRef.current(url, { method, body: JSON.stringify(body) });
  function submit(event: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<void>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    void run(async () => { await action(data); form.reset(); });
  }
  async function search(offset: number) {
    const term = offset === 0 ? query : searchedQuery;
    const data = await apiRef.current<SearchResult>(`/productivity/document-search?q=${encodeURIComponent(term)}&offset=${offset}`);
    setResult(previous => offset && previous ? { ...data, results: [...previous.results, ...data.results], warnings: [...previous.warnings, ...data.warnings], scanned: previous.scanned + data.scanned } : data);
    setSearchedQuery(term);
  }

  return <section className="productivity-panel">
    <div className="panel-toolbar"><div><h2>Espace de travail des dossiers</h2><p>Complétude, échanges, recherche documentaire et suivi des responsabilités.</p></div></div>
    <nav className="productivity-tabs" aria-label="Outils des dossiers">
      {[["case", "Dossier", ClipboardCheck], ["search", "Recherche documentaire", Search], ["blocks", "Blocages et relances", RefreshCw], ...(admin ? [["rules", "Règles et circuits", Settings]] : [])].map(([key, label, Icon]) => {
        const TabIcon = Icon as typeof Search;
        return <button key={String(key)} disabled={busy} className={tab === key ? "secondary-button" : "ghost-button"} aria-pressed={tab === key} onClick={() => setTab(String(key))} type="button"><TabIcon size={16} />{String(label)}</button>;
      })}
    </nav>
    {error && <p className="form-error" role="alert">{error}</p>}
    {message && <p role="status" className="app-message">{message}</p>}
    {busy && <p role="status">Traitement en cours… L’extraction documentaire peut prendre quelques minutes.</p>}

    {tab === "case" && <>
      <label className="productivity-selector">Dossier<select value={caseId} disabled={busy} onChange={e => setCaseId(e.target.value)}><option value="">Sélectionner un dossier</option>{selected && !cases.some(item => item.id === selected.id) && <option value={selected.id}>{selected.reference} — {selected.subject}</option>}{cases.map(item => <option key={item.id} value={item.id}>{item.reference} — {item.subject}</option>)}</select></label>
      {loading && <p role="status">Chargement du dossier…</p>}
      {caseId && <button type="button" disabled={busy || loading} className="ghost-button" onClick={() => void run(reloadCase)}><RefreshCw size={16} />Actualiser le dossier</button>}
      {!selected && <p className="empty-state">Créez ou sélectionnez un dossier pour accéder à ses outils.</p>}
      {selected && workspace && <div className="productivity-grid">
        <section className="productivity-card"><h3><ClipboardCheck size={18} /> Dossier complet avant transmission</h3>
          <p>Type : <strong>{workspace.checklist.request_type}</strong></p>
          {!workspace.checklist.configured && <p>Aucune règle documentaire configurée pour ce type de demande.</p>}
          {workspace.checklist.items.map(item => <p key={item.purpose}>{item.present ? "✓" : "○"} {item.purpose} — {item.present ? "Pièce présente" : "Pièce manquante"}</p>)}
          {workspace.checklist.configured && <p>{workspace.checklist.complete ? "Dossier complet" : "Transmission bloquée tant que les pièces obligatoires manquent."}</p>}
          {selected.status === "DRAFT" && sender && ["SYSTEM_ADMIN", "INSTITUTION_ADMIN", "AGENT"].includes(currentUser.role) && <form key={caseId} className="productivity-form" onSubmit={e => submit(e, async data => { await post(`${path}/type`, { request_type: data.get("request_type") }, "PATCH"); await reloadCase(); })}>
            <label>Type de demande<input name="request_type" defaultValue={workspace.checklist.request_type} required pattern="[A-Z0-9_]+" maxLength={80} list="policy-types" /></label><datalist id="policy-types">{Array.from(new Set(policies.map(p => p.request_type))).map(type => <option key={type} value={type} />)}</datalist>
            <button disabled={busy} className="ghost-button"><Save size={16} />Enregistrer le type</button>
          </form>}
          <p>Ajoutez les pièces depuis « Documents sécurisés », avec l’usage demandé dans la checklist.</p>
        </section>
        <section className="productivity-card"><h3><ShieldCheck size={18} /> Circuit de validation</h3>
          {!workspace.validation_steps.length ? <p>Validation hiérarchique simple. Les circuits configurés sont appliqués à la soumission d’une réponse.</p> : <ol>{workspace.validation_steps.map((step, i) => <li key={i}>{role(step)} — {workspace.validation_progress[i] ? `Validé le ${date(workspace.validation_progress[i].at)}` : i === workspace.validation_progress.length ? "Étape suivante" : "À venir"}</li>)}</ol>}
          {selected.status === "PENDING_VALIDATION" && receiver && ["SYSTEM_ADMIN", "INSTITUTION_ADMIN", "VALIDATOR"].includes(currentUser.role) && <form className="productivity-form" onSubmit={e => submit(e, async data => { await post(`/cases/${caseId}/validate`, { approved: data.get("decision") === "approve", comment: data.get("comment") }); await reloadCase(); setMessage("Décision enregistrée."); })}>
            <label>Décision<select name="decision"><option value="approve">Approuver l’étape</option><option value="reject">Rejeter la réponse</option></select></label><label>Commentaire<textarea name="comment" required maxLength={2000} /></label><button disabled={busy} className="primary-button"><CheckCircle2 size={16} />Enregistrer la décision</button>
          </form>}
          <p>Une personne différente valide chaque étape. Les règles de l’institution destinataire s’appliquent.</p>
        </section>
        <section className="productivity-card productivity-wide"><h3><MessageSquareText size={18} /> Discussion du dossier</h3>
          <p>Les notes internes restent dans votre institution. Les messages partagés sont visibles des deux institutions.</p>
          <div className="productivity-thread">{workspace.comments.length ? workspace.comments.map(comment => <article key={comment.id}><strong>{comment.author} · {comment.visibility === "INTERNAL" ? "Interne" : "Partagé"}</strong><small>{date(comment.created_at)}</small><p>{comment.body}</p></article>) : <p>Aucun message visible.</p>}</div>
          {writer && !["CLOSED", "ARCHIVED"].includes(selected.status) && <form className="productivity-form" onSubmit={e => submit(e, async data => { await post(`${path}/comments`, { body: data.get("body"), visibility: data.get("visibility"), mentions: data.getAll("mentions") }); await reloadCase(); setMessage("Message publié."); })}>
            <label>Visibilité<select name="visibility" defaultValue="INTERNAL"><option value="INTERNAL">Interne à mon institution</option><option value="SHARED" disabled={selected.status === "DRAFT"}>Partagé avec l’autre institution</option></select></label>
            <label>Message<textarea name="body" required maxLength={10000} rows={3} /></label>
            <label>Mentionner des collègues (sélection multiple)<select name="mentions" multiple>{workspace.members.filter(m => m.id !== currentUser.id).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
            <button className="primary-button" disabled={busy}><Send size={16} />Publier</button>
          </form>}
        </section>
        <section className="productivity-card productivity-wide"><h3><FileSearch size={18} /> Synthèse et proposition de réponse</h3>
          <p>Lecture locale des pièces, extraits sourcés et trame à compléter. Aucun envoi automatique.</p>
          <button type="button" className="secondary-button" disabled={busy} onClick={() => void run(async () => { const data = await apiRef.current<Summary>(`${path}/summary`, { method: "POST" }); setSummary(data); setProposal(data.proposal); })}><FileSearch size={16} />Préparer la synthèse</button>
          {summary && <><p className="preserve-text">{summary.overview}</p><p>{summary.coverage}</p>{summary.sources.map(source => <details key={source.attachment_id}><summary>{source.file_name}</summary><p>{source.coverage}</p><blockquote className="preserve-text">{source.excerpt || "Aucun texte extrait ; consultez la pièce originale."}</blockquote></details>)}
            {receiver && ["IN_PROGRESS", "REJECTED"].includes(selected.status) && (admin || (currentUser.role === "AGENT" && workspace.is_operator)) && <form className="productivity-form" onSubmit={e => { e.preventDefault(); void run(async () => { await post(`/cases/${caseId}/response`, { response_body: proposal }); await reloadCase(); setMessage("Proposition soumise au circuit de validation."); }); }}><label>Réponse à compléter et relire<textarea value={proposal} onChange={e => setProposal(e.target.value)} minLength={2} maxLength={10000} required rows={8} /></label><button disabled={busy} className="primary-button"><ShieldCheck size={16} />Soumettre à validation</button></form>}
          </>}
        </section>
        <section className="productivity-card"><h3><Users size={18} /> Délégation temporaire</h3><p>Le remplaçant peut traiter et répondre pendant la période indiquée, dans la limite de ses droits. Il ne reçoit pas de droit de validation.</p>
          {receiver && (admin || (currentUser.role === "AGENT" && workspace.is_operator)) && ["ASSIGNED", "APPROVED"].includes(selected.status) && <button className="secondary-button" disabled={busy} onClick={() => void run(async () => { await post(`/cases/${caseId}/${selected.status === "ASSIGNED" ? "start" : "send-response"}`, {}); await reloadCase(); setMessage("Dossier mis à jour."); })}><Send size={16} />{selected.status === "ASSIGNED" ? "Démarrer le traitement" : "Transmettre la réponse validée"}</button>}
          {workspace.delegations.map(d => <div key={d.id}><p>{d.delegate_name}<br />{date(d.starts_at)} → {date(d.ends_at)} · {d.revoked_at ? "Révoquée" : new Date(d.ends_at) <= new Date() ? "Expirée" : new Date(d.starts_at) > new Date() ? "Planifiée" : "Active"}</p>{admin && receiver && !d.revoked_at && <button className="ghost-button danger-button" disabled={busy} onClick={() => void run(async () => { await apiRef.current(`${path}/delegations/${d.id}`, { method: "DELETE" }); await reloadCase(); })}><X size={16} />Révoquer</button>}</div>)}
          {admin && receiver && selected.assigned_to && <form className="productivity-form" onSubmit={e => submit(e, async data => { await post(`${path}/delegations`, { delegate_id: data.get("delegate_id"), starts_at: new Date(String(data.get("starts_at"))).toISOString(), ends_at: new Date(String(data.get("ends_at"))).toISOString() }); await reloadCase(); })}>
            <label>Remplaçant<select name="delegate_id" required><option value="">Choisir un agent</option>{workspace.delegate_candidates.filter(m => m.id !== selected.assigned_to).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><label>Début<input name="starts_at" type="datetime-local" required /></label><label>Fin (90 jours maximum)<input name="ends_at" type="datetime-local" required /></label><button disabled={busy} className="secondary-button"><Users size={16} />Créer la délégation</button>
          </form>}
        </section>
        <section className="productivity-card"><h3><Archive size={18} /> Chronologie</h3>{workspace.timeline.length ? <ol>{workspace.timeline.map(event => <li key={event.id}><strong>{event.action}</strong><small>{date(event.created_at)}</small><p>{event.comment}</p></li>)}</ol> : <p>Aucune étape enregistrée.</p>}</section>
      </div>}
    </>}

    {tab === "search" && <section className="productivity-card"><h3><Search size={18} /> Rechercher dans les pièces</h3><p>PDF, scans, images, DOCX et texte. Analyse par lots de 5 pièces autorisées, limitée aux 10 premières pages de chaque PDF.</p>
      <form className="productivity-form" onSubmit={e => { e.preventDefault(); void run(() => search(0)); }}><label>Nom, référence ou expression<input value={query} onChange={e => setQuery(e.target.value)} minLength={2} maxLength={200} required /></label><button disabled={busy} className="primary-button"><Search size={16} />Rechercher</button></form>
      {result && <><p>{result.scanned} pièce(s) analysée(s) · {result.results.length} résultat(s).</p>{result.results.map((item, i) => <article className="productivity-result" key={i}><strong>{item.reference} · {item.file_name}</strong><p className="preserve-text">{item.excerpt}</p><small>{item.coverage}</small><button className="ghost-button" disabled={busy} onClick={() => { setCaseId(item.case_id); setTab("case"); }}><ClipboardCheck size={16} />Ouvrir le dossier</button></article>)}<details><summary>Couverture et limites d’extraction</summary>{result.warnings.map((w, i) => <p key={i}>{w.file_name} : {w.coverage}</p>)}</details>{result.next_offset !== null && <button className="secondary-button" disabled={busy} onClick={() => void run(() => search(result.next_offset!))}><RefreshCw size={16} />Analyser les pièces suivantes</button>}</>}
    </section>}

    {tab === "blocks" && <section className="productivity-card"><h3><RefreshCw size={18} /> Blocages et relances</h3><p>Le scanner d’échéances relance quotidiennement l’agent, puis alerte l’administrateur de l’institution après 24 h de retard et les administrateurs système après 72 h. Le scanner automatique doit être activé dans Gouvernance.</p><button className="ghost-button" disabled={busy} onClick={() => void run(async () => setBlocks(await apiRef.current<Block[]>("/productivity/bottlenecks")))}><RefreshCw size={16} />Actualiser</button>
      {!blocks.length && <p>Aucun blocage détecté parmi les dossiers accessibles.</p>}{blocks.map(block => <article className="productivity-result" key={block.id}><strong>{block.reference} — {block.subject}</strong><p>{block.reasons.join(" · ")} · {block.days_waiting} jour(s) sans évolution</p><button className="secondary-button" disabled={busy} onClick={() => { setCaseId(block.id); setTab("case"); }}><ClipboardCheck size={16} />Examiner</button></article>)}
    </section>}

    {tab === "rules" && admin && <section className="productivity-card"><h3><Settings size={18} /> Checklists et circuits configurables</h3><p>Les pièces obligatoires dépendent des règles de l’expéditeur. Les étapes de validation dépendent des règles du destinataire. Si plusieurs règles correspondent, elles se cumulent dans leur ordre de création.</p>
      <div className="productivity-thread">{policies.map(policy => <article key={policy.id}><strong>{policy.name} · {policy.request_type} · {policy.active ? "Active" : "Inactive"}</strong><p>{policy.required_purposes.join(", ") || "Aucune pièce obligatoire"} · {policy.validation_roles.map(role).join(" → ") || "Validation simple"}</p><button className="ghost-button" disabled={busy} onClick={() => { setEditingPolicy(policy); setPolicyVersion(v => v + 1); }}><Settings size={16} />Modifier</button></article>)}</div>
      <button className="ghost-button" disabled={busy} onClick={() => { setEditingPolicy(null); setPolicyVersion(v => v + 1); }}><Plus size={16} />Nouvelle règle</button>
      <form key={`${editingPolicy?.id ?? "new"}-${policyVersion}`} className="productivity-form" onSubmit={e => submit(e, async data => {
        const values = { name: data.get("name"), institution_id: data.get("institution_id"), request_type: data.get("request_type"), classification: data.get("classification") || null, required_purposes: String(data.get("purposes")).split(",").map(s => s.trim()).filter(Boolean), validation_roles: data.getAll("step").filter(Boolean), active: data.get("active") === "on" };
        await post(`/productivity/policies${editingPolicy ? `/${editingPolicy.id}` : ""}`, values, editingPolicy ? "PUT" : "POST");
        setPolicies(await apiRef.current<Policy[]>("/productivity/policies")); setEditingPolicy(null); setPolicyVersion(v => v + 1); setMessage("Règle enregistrée.");
      })}>
        <h4>{editingPolicy ? "Modifier la règle" : "Créer une règle"}</h4>
        <label>Nom<input name="name" defaultValue={editingPolicy?.name} required minLength={2} maxLength={150} /></label>
        <label>Institution<select name="institution_id" defaultValue={editingPolicy?.institution_id ?? currentUser.institution_id}>{institutions.filter(i => currentUser.role === "SYSTEM_ADMIN" || i.id === currentUser.institution_id).map(i => <option key={i.id} value={i.id}>{i.name}</option>)}</select></label>
        <label>Type de demande<input name="request_type" defaultValue={editingPolicy?.request_type ?? "GENERAL"} pattern="[A-Z0-9_]+" maxLength={80} required /></label>
        <label>Classification<select name="classification" defaultValue={editingPolicy?.classification ?? ""}><option value="">Toutes</option>{["PUBLIC", "INTERNE", "CONFIDENTIEL", "SECRET"].map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Usages des pièces obligatoires, séparés par une virgule<input name="purposes" defaultValue={editingPolicy?.required_purposes.join(", ")} placeholder="REQUEST, EVIDENCE" /></label>
        <p>Utilisez les codes d’usage disponibles dans les référentiels documentaires.</p>
        {[0, 1, 2, 3, 4].map(i => <label key={i}>Validation — étape {i + 1}<select name="step" defaultValue={editingPolicy?.validation_roles[i] ?? ""}><option value="">Aucune</option><option value="VALIDATOR">Validateur</option><option value="INSTITUTION_ADMIN">Admin institution</option></select></label>)}
        <label><input type="checkbox" name="active" defaultChecked={editingPolicy?.active ?? true} /> Règle active</label>
        <button className="primary-button" disabled={busy}><Save size={16} />Enregistrer la règle</button>
      </form>
    </section>}
  </section>;
}
