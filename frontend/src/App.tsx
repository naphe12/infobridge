import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpRight,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  Database,
  Download,
  Eye,
  EyeOff,
  FileCheck2,
  FileSearch,
  FileText,
  FilePlus2,
  Fingerprint,
  History,
  Inbox,
  KeyRound,
  LayoutDashboard,
  LockKeyhole,
  LogIn,
  LogOut,
  Mail,
  MessageSquareText,
  MoreHorizontal,
  Search,
  Send,
  ServerCog,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  UserCheck,
  Users,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

type Dashboard = {
  institutions: number;
  users: number;
  cases: number;
  security_events: number;
  closed_cases?: number;
  response_rate?: number;
};

type CaseItem = {
  reference: string;
  subject: string;
  sender: string;
  receiver: string;
  status: "En revue" | "Reçu" | "Approuvé" | "Urgent";
  classification: "Interne" | "Confidentiel" | "Secret";
  owner: string;
  due: string;
  progress: number;
};

type AppSection = "overview" | "admin" | "documents";
type UserRole = "admin" | "user";
type FeatureKey =
  | "access"
  | "new-case"
  | "cases"
  | "classification"
  | "upload-document"
  | "secure-transmission"
  | "receive-assign"
  | "processing"
  | "validation"
  | "secure-response"
  | "lifecycle"
  | "retention"
  | "audit"
  | "backup"
  | "notifications"
  | "search"
  | "dashboard"
  | "admin-users"
  | "invite-user"
  | "admin-institutions"
  | "create-institution"
  | "admin-governance"
  | "integrations";

type AuthUser = {
  id: string;
  institution_id: string;
  full_name: string;
  email: string;
  role: "SYSTEM_ADMIN" | "INSTITUTION_ADMIN" | "AGENT" | "VALIDATOR" | "OBSERVER" | "AUDITOR";
};

type LoginResponse = {
  access_token: string;
  expires_in: number;
  user: AuthUser;
};

type Institution = {
  id: string;
  name: string;
  code: string;
  type: string;
  status: string;
};

type PlatformUser = {
  id: string;
  institution_id: string;
  full_name: string;
  email: string;
  role: AuthUser["role"];
  status: string;
  mfa_enabled: boolean;
};

type ExchangeCase = {
  id: string;
  reference: string;
  subject: string;
  description: string | null;
  sender_institution_id: string;
  receiver_institution_id: string;
  status: string;
  priority: string;
  classification: string;
  assigned_to: string | null;
  due_at: string | null;
  created_at: string;
};

type Attachment = {
  id: string;
  case_id: string | null;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  purpose: string;
  encrypted: boolean;
  uploaded_at: string;
};

type WorkflowDraft =
  | { mode: "response"; caseId: string; title: string }
  | { mode: "validate"; caseId: string; title: string; approved: boolean }
  | null;

type AdminDraft = "institution" | "user" | null;

type QuickAccessAction = {
  description: string;
  feature: FeatureKey;
  icon: typeof LayoutDashboard;
  label: string;
};

type QuickAccessGroup = {
  actions: QuickAccessAction[];
  description: string;
  icon: typeof LayoutDashboard;
  key: string;
  title: string;
  tone: "teal" | "amber" | "blue" | "rose" | "slate";
};

const cases: CaseItem[] = [
  {
    reference: "IB-2026-0048",
    subject: "Validation d'identité institutionnelle",
    sender: "Ministère des Finances",
    receiver: "Banque Centrale",
    status: "En revue",
    classification: "Confidentiel",
    owner: "A. Niyonzima",
    due: "Aujourd'hui, 16:30",
    progress: 72,
  },
  {
    reference: "IB-2026-0047",
    subject: "Transmission de pièces justificatives",
    sender: "Commune de Bujumbura",
    receiver: "Agence Nationale",
    status: "Reçu",
    classification: "Interne",
    owner: "C. Irakoze",
    due: "Demain, 09:00",
    progress: 45,
  },
  {
    reference: "IB-2026-0046",
    subject: "Demande de rapprochement documentaire",
    sender: "Office des Recettes",
    receiver: "Ministère de la Justice",
    status: "Urgent",
    classification: "Secret",
    owner: "D. Bigirimana",
    due: "Dans 2 h",
    progress: 28,
  },
  {
    reference: "IB-2026-0045",
    subject: "Accusé de réception pour décision archivée",
    sender: "Agence Nationale",
    receiver: "Ministère de l'Intérieur",
    status: "Approuvé",
    classification: "Confidentiel",
    owner: "L. Hakizimana",
    due: "Clôturé",
    progress: 100,
  },
];

const auditTrail = [
  { label: "Signature vérifiée", detail: "IB-2026-0048", tone: "success" },
  { label: "Connexion sensible", detail: "Banque Centrale", tone: "warning" },
  { label: "Pièce jointe chiffrée", detail: "2 documents", tone: "neutral" },
];

const navItems = [
  { id: "overview", label: "Vue d'ensemble", icon: LayoutDashboard },
  { id: "admin", label: "Administration", icon: Settings },
  { id: "documents", label: "Documents", icon: FileText },
] satisfies Array<{ id: AppSection; label: string; icon: typeof LayoutDashboard }>;

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => sessionStorage.getItem("infobridge_session") === "active");
  const [accessToken, setAccessToken] = useState(() => sessionStorage.getItem("infobridge_token") ?? "");
  const [userRole, setUserRole] = useState<UserRole>(() =>
    sessionStorage.getItem("infobridge_role") === "admin" ? "admin" : "user",
  );
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => {
    const storedUser = sessionStorage.getItem("infobridge_user");
    return storedUser ? (JSON.parse(storedUser) as AuthUser) : null;
  });
  const [activeSection, setActiveSection] = useState<AppSection>(() =>
    sessionStorage.getItem("infobridge_role") === "admin" ? "admin" : "documents",
  );
  const [loginError, setLoginError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [appMessage, setAppMessage] = useState("");
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [exchangeCases, setExchangeCases] = useState<ExchangeCase[]>([]);
  const [attachmentsByCase, setAttachmentsByCase] = useState<Record<string, Attachment[]>>({});
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft>(null);
  const [adminDraft, setAdminDraft] = useState<AdminDraft>(null);
  const [activeFeature, setActiveFeature] = useState<FeatureKey | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard>({
    institutions: 0,
    users: 0,
    cases: 0,
    security_events: 0,
  });

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    void loadWorkspaceData();
  }, [accessToken, isAuthenticated, userRole]);

  async function apiFetch<T>(path: string, init: RequestInit = {}) {
    const response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init.headers,
      },
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(payload?.detail ?? `Erreur API ${response.status}`);
    }

    return (await response.json()) as T;
  }

  async function loadWorkspaceData() {
    try {
      const [dashboardData, caseData, institutionData] = await Promise.all([
        apiFetch<Dashboard>("/dashboard"),
        apiFetch<ExchangeCase[]>("/cases"),
        apiFetch<Institution[]>("/institutions"),
      ]);

      setDashboard(dashboardData);
      setExchangeCases(caseData);
      setInstitutions(institutionData);

      if (userRole === "admin") {
        setUsers(await apiFetch<PlatformUser[]>("/users"));
      }

      const attachmentPairs = await Promise.all(
        caseData.map(async (item) => [item.id, await apiFetch<Attachment[]>(`/cases/${item.id}/attachments`)] as const),
      );
      setAttachmentsByCase(Object.fromEntries(attachmentPairs));
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Impossible de charger les données.");
    }
  }

  const metrics = useMemo(
    () => [
      {
        icon: Building2,
        label: "Institutions",
        value: dashboard.institutions,
        delta: "+4 ce mois",
      },
      {
        icon: FileCheck2,
        label: "Dossiers actifs",
        value: dashboard.cases,
        delta: "18 en revue",
      },
      {
        icon: Users,
        label: "Utilisateurs",
        value: dashboard.users,
        delta: "92% MFA",
      },
      {
        icon: AlertTriangle,
        label: "Alertes sécurité",
        value: dashboard.security_events,
        delta: "3 critiques",
      },
    ],
    [dashboard],
  );

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    if (!email || !password) {
      setLoginError("Renseignez votre adresse e-mail et votre mot de passe.");
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/auth/login`, {
        body: JSON.stringify({ email, password }),
        headers: {
          "Content-Type": "application/json",
        },
        method: "POST",
      });

      if (!response.ok) {
        if (response.status === 401) {
          setLoginError("Identifiants incorrects.");
          return;
        }

        const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setLoginError(errorPayload?.detail ?? `Erreur API ${response.status}.`);
        return;
      }

      const data = (await response.json()) as LoginResponse;
      const role = isAdminRole(data.user.role) ? "admin" : "user";

      sessionStorage.setItem("infobridge_session", "active");
      sessionStorage.setItem("infobridge_token", data.access_token);
      sessionStorage.setItem("infobridge_role", role);
      sessionStorage.setItem("infobridge_user", JSON.stringify(data.user));
      setAccessToken(data.access_token);
      setCurrentUser(data.user);
      setUserRole(role);
      setActiveSection(role === "admin" ? "admin" : "documents");
      setLoginError("");
      setIsAuthenticated(true);
      setAppMessage("");
    } catch {
      setLoginError(`API injoignable. Vérifiez VITE_API_URL: ${apiUrl}`);
    }
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentUser) {
      return;
    }

    const formData = new FormData(event.currentTarget);
    const file = formData.get("file");
    const payload = {
      reference: String(formData.get("reference") ?? "").trim(),
      subject: String(formData.get("subject") ?? "").trim(),
      description: String(formData.get("description") ?? "").trim() || null,
      sender_institution_id: currentUser.institution_id,
      receiver_institution_id: String(formData.get("receiver_institution_id") ?? ""),
      priority: String(formData.get("priority") ?? "NORMAL"),
      classification: String(formData.get("classification") ?? "INTERNE"),
    };

    try {
      const createdCase = await apiFetch<ExchangeCase>("/cases", {
        body: JSON.stringify(payload),
        method: "POST",
      });

      if (file instanceof File && file.size > 0) {
        const upload = new FormData();
        upload.append("file", file);
        upload.append("purpose", "REQUEST");
        await apiFetch<Attachment>(`/cases/${createdCase.id}/attachments`, {
          body: upload,
          method: "POST",
        });
      }

      event.currentTarget.reset();
      setActiveFeature("cases");
      setAppMessage(`Demande ${createdCase.reference} créée avec succès.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Création impossible.");
    }
  }

  async function handleUploadAttachment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const caseId = String(formData.get("case_id") ?? "");
    const file = formData.get("file");

    if (!(file instanceof File) || file.size === 0 || !caseId) {
      setAppMessage("Sélectionnez une demande et un fichier.");
      return;
    }

    try {
      const upload = new FormData();
      upload.append("file", file);
      upload.append("purpose", "RESPONSE");
      await apiFetch<Attachment>(`/cases/${caseId}/attachments`, {
        body: upload,
        method: "POST",
      });
      event.currentTarget.reset();
      setActiveFeature("cases");
      setAppMessage("Pièce jointe chiffrée téléversée.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Téléversement impossible.");
    }
  }

  async function handleCreateInstitution(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = {
      code: String(formData.get("code") ?? "").trim(),
      name: String(formData.get("name") ?? "").trim(),
      type: String(formData.get("type") ?? "AGENCY"),
    };

    try {
      const institution = await apiFetch<Institution>("/institutions", {
        body: JSON.stringify(payload),
        method: "POST",
      });
      event.currentTarget.reset();
      setAdminDraft(null);
      setActiveFeature("admin-institutions");
      setAppMessage(`Institution ${institution.name} créée.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Création institution impossible.");
    }
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = {
      email: String(formData.get("email") ?? "").trim(),
      full_name: String(formData.get("full_name") ?? "").trim(),
      institution_id: String(formData.get("institution_id") ?? ""),
      password: String(formData.get("password") ?? ""),
      role: String(formData.get("role") ?? "AGENT"),
    };

    try {
      const user = await apiFetch<PlatformUser>("/users", {
        body: JSON.stringify(payload),
        method: "POST",
      });
      event.currentTarget.reset();
      setAdminDraft(null);
      setActiveFeature("admin-users");
      setAppMessage(`Utilisateur ${user.full_name} créé.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Création utilisateur impossible.");
    }
  }

  async function handleWorkflowAction(caseId: string, action: "send" | "receive" | "send-response" | "close") {
    try {
      await apiFetch<ExchangeCase>(`/cases/${caseId}/${action}`, {
        method: "POST",
      });
      setAppMessage("Action effectuée avec succès.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Action impossible.");
    }
  }

  async function handleAssignCase(caseId: string, assignedTo: string) {
    if (!assignedTo) {
      setAppMessage("Sélectionnez un utilisateur à affecter.");
      return;
    }

    try {
      await apiFetch<ExchangeCase>(`/cases/${caseId}/assign`, {
        body: JSON.stringify({ assigned_to: assignedTo }),
        method: "POST",
      });
      setAppMessage("Demande affectée.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Affectation impossible.");
    }
  }

  function openDraftResponse(caseId: string) {
    const exchangeCase = exchangeCases.find((item) => item.id === caseId);
    setWorkflowDraft({
      caseId,
      mode: "response",
      title: exchangeCase ? `Réponse à ${exchangeCase.reference}` : "Réponse proposée",
    });
  }

  function openValidation(caseId: string, approved: boolean) {
    const exchangeCase = exchangeCases.find((item) => item.id === caseId);
    setWorkflowDraft({
      approved,
      caseId,
      mode: "validate",
      title: `${approved ? "Valider" : "Rejeter"} ${exchangeCase?.reference ?? "la réponse"}`,
    });
  }

  async function handleWorkflowDraftSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workflowDraft) {
      return;
    }

    const formData = new FormData(event.currentTarget);
    const body = String(formData.get("body") ?? "").trim();

    if (!body) {
      setAppMessage("Renseignez le champ avant de confirmer.");
      return;
    }

    try {
      if (workflowDraft.mode === "response") {
        await apiFetch<ExchangeCase>(`/cases/${workflowDraft.caseId}/response`, {
          body: JSON.stringify({ response_body: body }),
          method: "POST",
        });
        setAppMessage("Réponse envoyée en validation.");
      } else {
        await apiFetch<ExchangeCase>(`/cases/${workflowDraft.caseId}/validate`, {
          body: JSON.stringify({ approved: workflowDraft.approved, comment: body }),
          method: "POST",
        });
        setAppMessage(workflowDraft.approved ? "Réponse validée." : "Réponse rejetée.");
      }

      setWorkflowDraft(null);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Action impossible.");
    }
  }

  function openFeature(feature: FeatureKey) {
    const section = getFeatureSection(feature, userRole === "admin");
    setActiveSection(section);
    setActiveFeature(feature);
    setWorkflowDraft(null);

    if (feature === "invite-user") {
      setAdminDraft("user");
      return;
    }

    if (feature === "create-institution") {
      setAdminDraft("institution");
      return;
    }

    setAdminDraft(null);
  }

  function handleLogout() {
    sessionStorage.removeItem("infobridge_session");
    sessionStorage.removeItem("infobridge_token");
    sessionStorage.removeItem("infobridge_role");
    sessionStorage.removeItem("infobridge_user");
    setIsAuthenticated(false);
    setAccessToken("");
    setCurrentUser(null);
    setUserRole("user");
    setActiveSection("documents");
  }

  if (!isAuthenticated) {
    return (
      <main className="login-shell">
        <section className="login-visual" aria-label="Présentation InfoBridge">
          <div className="login-brand">
            <span className="brand-mark">
              <ShieldCheck size={22} />
            </span>
            <span>InfoBridge</span>
          </div>
          <div className="login-copy">
            <span className="section-label">Accès sécurisé</span>
            <h1>Connexion au centre de coordination</h1>
            <p>
              Suivez les échanges sensibles, vérifiez les dossiers institutionnels et gardez une trace claire de chaque
              décision.
            </p>
          </div>
          <div className="login-assurance">
            <div>
              <Fingerprint size={20} />
              <span>Contrôle d'identité</span>
            </div>
            <div>
              <LockKeyhole size={20} />
              <span>Session protégée</span>
            </div>
            <div>
              <Archive size={20} />
              <span>Journal d'audit</span>
            </div>
          </div>
        </section>

        <section className="login-panel" aria-label="Formulaire de connexion">
          <div className="login-card">
            <div className="login-card-header">
              <span className="login-icon">
                <LogIn size={20} />
              </span>
              <div>
                <h2>Se connecter</h2>
                <p>Utilisez votre compte institutionnel.</p>
              </div>
            </div>

            <form className="login-form" onSubmit={handleLogin}>
              <label>
                <span>Adresse e-mail</span>
                <div className="input-control">
                  <Mail size={18} />
                  <input name="email" placeholder="nom@institution.gov.bi" type="email" />
                </div>
              </label>

              <label>
                <span>Mot de passe</span>
                <div className="input-control">
                  <LockKeyhole size={18} />
                  <input name="password" placeholder="Mot de passe" type={showPassword ? "text" : "password"} />
                  <button
                    aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                    className="password-toggle"
                    onClick={() => setShowPassword((value) => !value)}
                    type="button"
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </label>

              <div className="login-options">
                <label className="remember-option">
                  <input type="checkbox" />
                  <span>Garder la session active</span>
                </label>
                <a href="/">Mot de passe oublié</a>
              </div>

              {loginError ? <p className="form-error">{loginError}</p> : null}

              <button className="primary-button login-submit" type="submit">
                <LogIn size={18} />
                Accéder à InfoBridge
              </button>
            </form>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Navigation principale">
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck size={22} />
          </span>
          <span>InfoBridge</span>
        </div>

        <button className="danger-logout-button" onClick={handleLogout} type="button">
          <LogOut size={18} />
          Se déconnecter
        </button>

        <nav className="nav-list">
          {getVisibleNavItems(userRole).map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={activeSection === item.id ? "active" : undefined}
                key={item.label}
                onClick={() => {
                  setActiveSection(item.id);
                  setActiveFeature(null);
                  setAdminDraft(null);
                }}
                type="button"
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="side-status">
          <div className="status-dot" />
          <div>
            <strong>Système opérationnel</strong>
            <span>API synchronisée</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="section-label">{userRole === "admin" ? "Profil administrateur" : "Profil utilisateur"}</span>
            <h1>{getSectionTitle(activeSection)}</h1>
            {currentUser ? <p className="user-context">{currentUser.full_name} · {currentUser.email}</p> : null}
          </div>

          <div className="topbar-actions">
            <label className="search-field">
              <Search size={18} />
              <input aria-label="Rechercher" placeholder="Rechercher un dossier, une institution..." type="search" />
            </label>
            <button aria-label="Notifications" className="icon-button" type="button">
              <Bell size={18} />
            </button>
            <button
              className="primary-button"
              onClick={() => {
                if (activeSection === "admin") {
                  setActiveFeature("invite-user");
                  setAdminDraft("user");
                  return;
                }
                openFeature(activeSection === "documents" ? "upload-document" : "new-case");
              }}
              type="button"
            >
              {activeSection === "documents" ? <UploadCloud size={18} /> : activeSection === "admin" ? <Users size={18} /> : <FilePlus2 size={18} />}
              {activeSection === "documents"
                ? "Déposer un document"
                : activeSection === "admin"
                  ? "Nouvel utilisateur"
                  : "Nouveau dossier"}
            </button>
          </div>
        </header>

        <QuickAccessPanel isAdmin={userRole === "admin"} onOpenFeature={openFeature} />

        {activeSection === "overview" ? <Overview metrics={metrics} /> : null}
        {appMessage ? <p className="app-message">{appMessage}</p> : null}
        {activeSection === "admin" ? (
          <AdminWorkspace
            adminDraft={adminDraft}
            dashboard={dashboard}
            institutions={institutions}
            onCancelAdminDraft={() => setAdminDraft(null)}
            onCreateInstitution={handleCreateInstitution}
            onCreateUser={handleCreateUser}
            activeFeature={activeFeature}
            onOpenAdminDraft={setAdminDraft}
            users={users}
          />
        ) : null}
        {activeSection === "documents" ? (
          <DocumentsWorkspace
            attachmentsByCase={attachmentsByCase}
            activeFeature={activeFeature}
            currentUser={currentUser}
            exchangeCases={exchangeCases}
            institutions={institutions}
            onAssignCase={handleAssignCase}
            onCreateCase={handleCreateCase}
            onDraftResponse={openDraftResponse}
            onUploadAttachment={handleUploadAttachment}
            onValidateResponse={openValidation}
            onWorkflowAction={handleWorkflowAction}
            onWorkflowDraftCancel={() => setWorkflowDraft(null)}
            onWorkflowDraftSubmit={handleWorkflowDraftSubmit}
            users={users}
            workflowDraft={workflowDraft}
          />
        ) : null}
      </section>
    </main>
  );
}

function QuickAccessPanel({
  isAdmin,
  onOpenFeature,
}: {
  isAdmin: boolean;
  onOpenFeature: (feature: FeatureKey) => void;
}) {
  const groups = useMemo(() => getQuickAccessGroups(isAdmin), [isAdmin]);
  const [activeGroupKey, setActiveGroupKey] = useState<string | null>(null);
  const activeGroup = groups.find((group) => group.key === activeGroupKey) ?? null;

  return (
    <section className="quick-access-panel" aria-label="Accès rapides">
      <div className="quick-access-grid">
        {groups.map((group) => {
          const Icon = group.icon;
          return (
            <button
              className={`quick-access-card ${group.tone}`}
              key={group.key}
              onClick={() => setActiveGroupKey(group.key)}
              type="button"
            >
              <span className="quick-access-icon">
                <Icon size={20} />
              </span>
              <span>
                <strong>{group.title}</strong>
                <small>{group.description}</small>
                <em>{group.actions.length} accès</em>
              </span>
            </button>
          );
        })}
      </div>

      {activeGroup ? (
        <div className="quick-action-overlay" onClick={() => setActiveGroupKey(null)}>
          <div className="quick-action-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="quick-action-drawer-header">
              <div>
                <span className="section-label">Groupe</span>
                <h2>{activeGroup.title}</h2>
                <p>{activeGroup.description}</p>
              </div>
              <button aria-label="Fermer" className="icon-button" onClick={() => setActiveGroupKey(null)} type="button">
                <X size={18} />
              </button>
            </div>
            <div className="quick-action-list">
              {activeGroup.actions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    className="quick-action-item"
                    key={action.feature}
                    onClick={() => {
                      onOpenFeature(action.feature);
                      setActiveGroupKey(null);
                    }}
                    type="button"
                  >
                    <span className="quick-access-icon">
                      <Icon size={19} />
                    </span>
                    <span>
                      <strong>{action.label}</strong>
                      <small>{action.description}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function getQuickAccessGroups(isAdmin: boolean): QuickAccessGroup[] {
  const adminActions: QuickAccessAction[] = isAdmin
    ? [
        {
          description: "Créer un compte et attribuer un rôle",
          feature: "invite-user",
          icon: UserCheck,
          label: "Inviter utilisateur",
        },
        {
          description: "Liste des comptes et profils d'accès",
          feature: "admin-users",
          icon: Users,
          label: "Utilisateurs",
        },
        {
          description: "Créer une institution participante",
          feature: "create-institution",
          icon: Building2,
          label: "Nouvelle institution",
        },
        {
          description: "Organismes autorisés sur la plateforme",
          feature: "admin-institutions",
          icon: Building2,
          label: "Institutions",
        },
        {
          description: "Règles de gouvernance et politiques",
          feature: "admin-governance",
          icon: Settings,
          label: "Gouvernance",
        },
      ]
    : [];

  return [
    {
      actions: [
        { description: "Connexion, rôles et droits d'accès", feature: "access", icon: KeyRound, label: "Accès" },
        { description: "Créer une demande d'information", feature: "new-case", icon: FilePlus2, label: "Nouvelle demande" },
        { description: "Consulter et suivre les dossiers", feature: "cases", icon: Inbox, label: "Dossiers" },
        { description: "Catégoriser la sensibilité des informations", feature: "classification", icon: ShieldCheck, label: "Classification" },
      ],
      description: "Authentification, dossiers et classement de l'information.",
      icon: LayoutDashboard,
      key: "core",
      title: "Coeur métier",
      tone: "teal",
    },
    {
      actions: [
        { description: "Téléverser des pièces chiffrées", feature: "upload-document", icon: UploadCloud, label: "Documents sécurisés" },
        { description: "Transmission protégée entre institutions", feature: "secure-transmission", icon: Send, label: "Transmission" },
        { description: "Réception et affectation aux agents", feature: "receive-assign", icon: UserCheck, label: "Réception" },
        { description: "Réponse sécurisée après validation", feature: "secure-response", icon: Mail, label: "Réponse sécurisée" },
      ],
      description: "Échanges, chiffrement, envoi et réception des dossiers.",
      icon: LockKeyhole,
      key: "secure-exchange",
      title: "Échanges sécurisés",
      tone: "blue",
    },
    {
      actions: [
        { description: "Traitement opérationnel des demandes", feature: "processing", icon: Workflow, label: "Traitement" },
        { description: "Validation hiérarchique avant envoi", feature: "validation", icon: ClipboardCheck, label: "Validation" },
        { description: "Suivi de la création à la clôture", feature: "lifecycle", icon: History, label: "Cycle de vie" },
        { description: "Conservation et archivage des dossiers", feature: "retention", icon: Archive, label: "Conservation" },
      ],
      description: "Affectation, traitement, validation et clôture.",
      icon: Workflow,
      key: "workflow",
      title: "Workflow",
      tone: "amber",
    },
    {
      actions: [
        { description: "Actions et événements de plateforme", feature: "audit", icon: FileSearch, label: "Journalisation" },
        { description: "Sauvegarde et reprise après incident", feature: "backup", icon: Database, label: "Sauvegarde" },
        { description: "Notifications et alertes utilisateurs", feature: "notifications", icon: Bell, label: "Alertes" },
        { description: "Recherche transverse des dossiers", feature: "search", icon: Search, label: "Recherche" },
        { description: "Statistiques et taux de réponse", feature: "dashboard", icon: BarChart3, label: "Statistiques" },
      ],
      description: "Audit, supervision, recherche et indicateurs.",
      icon: Activity,
      key: "supervision",
      title: "Pilotage",
      tone: "rose",
    },
    {
      actions: [
        ...adminActions,
        { description: "Échanges avec d'autres systèmes", feature: "integrations", icon: ServerCog, label: "Interopérabilité" },
      ],
      description: "Administration plateforme et intégrations.",
      icon: ServerCog,
      key: "platform",
      title: "Plateforme",
      tone: "slate",
    },
  ];
}

function getFeatureSection(feature: FeatureKey, isAdmin: boolean): AppSection {
  if (feature === "dashboard") {
    return "overview";
  }

  if (
    [
      "admin-users",
      "invite-user",
      "admin-institutions",
      "create-institution",
      "admin-governance",
      "integrations",
      "backup",
      "audit",
    ].includes(feature) &&
    isAdmin
  ) {
    return "admin";
  }

  return "documents";
}

function getFeatureTitle(feature: FeatureKey) {
  const titles: Record<FeatureKey, string> = {
    access: "Authentification et accès",
    "new-case": "Création de demande",
    cases: "Gestion des demandes",
    classification: "Classification de l'information",
    "upload-document": "Gestion sécurisée des documents",
    "secure-transmission": "Transmission sécurisée",
    "receive-assign": "Réception et affectation",
    processing: "Traitement des demandes",
    validation: "Validation hiérarchique",
    "secure-response": "Envoi sécurisé des réponses",
    lifecycle: "Cycle de vie des dossiers",
    retention: "Conservation",
    audit: "Journalisation",
    backup: "Sauvegarde et reprise",
    notifications: "Notifications et alertes",
    search: "Recherche",
    dashboard: "Tableau de bord et statistiques",
    "admin-users": "Administration des utilisateurs",
    "invite-user": "Inviter un utilisateur",
    "admin-institutions": "Administration des institutions",
    "create-institution": "Créer une institution",
    "admin-governance": "Administration de la plateforme",
    integrations: "Interopérabilité",
  };

  return titles[feature];
}

function getFeatureDescription(feature: FeatureKey | null) {
  if (!feature) {
    return "Accès contrôlé aux demandes et pièces téléversées";
  }

  const descriptions: Partial<Record<FeatureKey, string>> = {
    classification: "Filtrez et vérifiez les niveaux de sensibilité des demandes.",
    "receive-assign": "Réceptionnez les demandes entrantes puis affectez-les aux agents.",
    processing: "Suivez les dossiers à traiter et rédigez les réponses.",
    "secure-response": "Envoyez les réponses validées par le circuit hiérarchique.",
    "secure-transmission": "Transmettez les demandes en conservant la traçabilité.",
    validation: "Validez ou rejetez les réponses avant leur transmission.",
    lifecycle: "Pilotez chaque dossier jusqu'à clôture.",
  };

  return descriptions[feature] ?? "Accès contrôlé aux demandes et pièces téléversées";
}

function FeatureIntro({ description, icon, title }: { description: string; icon: ReactNode; title: string }) {
  return (
    <section className="feature-intro-panel">
      <span className="feature-intro-icon">{icon}</span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </section>
  );
}

function CapabilityPanel({ feature }: { feature: FeatureKey }) {
  return (
    <section className="capability-panel">
      <div className="panel-toolbar">
        <div>
          <h2>{getFeatureTitle(feature)}</h2>
          <p>Module prévu dans la trajectoire fonctionnelle InfoBridge.</p>
        </div>
      </div>
      <div className="capability-body">
        <StatusPill label="À brancher" />
        <p>
          L'accès rapide est déjà présent pour structurer l'interface. La prochaine étape consiste à relier ce module à
          ses écrans et endpoints dédiés.
        </p>
      </div>
    </section>
  );
}

function Overview({ metrics }: { metrics: Array<{ icon: typeof Building2; label: string; value: number; delta: string }> }) {
  return (
    <>
      <section className="metric-grid" aria-label="Indicateurs">
        {metrics.map((metric) => (
          <MetricCard
            icon={<metric.icon size={21} />}
            key={metric.label}
            label={metric.label}
            value={metric.value}
            delta={metric.delta}
          />
        ))}
      </section>

      <section className="main-grid">
        <CaseQueue />
        <InsightRail />
      </section>
    </>
  );
}

function AdminWorkspace({
  activeFeature,
  adminDraft,
  dashboard,
  institutions,
  onCancelAdminDraft,
  onCreateInstitution,
  onCreateUser,
  onOpenAdminDraft,
  users,
}: {
  activeFeature: FeatureKey | null;
  adminDraft: AdminDraft;
  dashboard: Dashboard;
  institutions: Institution[];
  onCancelAdminDraft: () => void;
  onCreateInstitution: (event: FormEvent<HTMLFormElement>) => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => void;
  onOpenAdminDraft: (draft: AdminDraft) => void;
  users: PlatformUser[];
}) {
  return (
    <section className="admin-layout">
      {adminDraft ? (
        <section className="settings-panel">
          <div className="panel-toolbar">
            <div>
              <h2>{adminDraft === "institution" ? "Nouvelle institution" : "Nouvel utilisateur"}</h2>
              <p>
                {adminDraft === "institution"
                  ? "Enregistrer une institution participante."
                  : "Créer un compte et lui attribuer un rôle."}
              </p>
            </div>
            <button className="ghost-button" onClick={onCancelAdminDraft} type="button">
              Annuler
            </button>
          </div>

          {adminDraft === "institution" ? (
            <form className="request-form admin-form" onSubmit={onCreateInstitution}>
              <label>
                <span>Nom</span>
                <input name="name" placeholder="Ministère, agence, banque..." required />
              </label>
              <label>
                <span>Code</span>
                <input name="code" placeholder="MINFIN" required />
              </label>
              <label>
                <span>Type</span>
                <select name="type">
                  <option value="MINISTRY">Ministère</option>
                  <option value="BANK">Banque</option>
                  <option value="COMMUNE">Commune</option>
                  <option value="AGENCY">Agence</option>
                  <option value="OPERATOR">Opérateur</option>
                  <option value="PRIVATE">Privé</option>
                  <option value="OTHER">Autre</option>
                </select>
              </label>
              <button className="primary-button" type="submit">
                <Building2 size={18} />
                Créer institution
              </button>
            </form>
          ) : (
            <form className="request-form admin-form" onSubmit={onCreateUser}>
              <label>
                <span>Nom complet</span>
                <input name="full_name" placeholder="Nom de l'utilisateur" required />
              </label>
              <label>
                <span>E-mail</span>
                <input name="email" placeholder="user@institution.bi" required type="email" />
              </label>
              <label>
                <span>Mot de passe initial</span>
                <input name="password" minLength={12} placeholder="Mot de passe temporaire" required type="password" />
              </label>
              <label>
                <span>Institution</span>
                <select name="institution_id" required>
                  <option value="">Sélectionner</option>
                  {institutions.map((institution) => (
                    <option key={institution.id} value={institution.id}>
                      {institution.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Rôle</span>
                <select name="role">
                  <option value="AGENT">Agent</option>
                  <option value="VALIDATOR">Validateur</option>
                  <option value="OBSERVER">Observateur</option>
                  <option value="AUDITOR">Auditeur</option>
                  <option value="INSTITUTION_ADMIN">Admin institution</option>
                </select>
              </label>
              <button className="primary-button" type="submit">
                <Users size={18} />
                Créer utilisateur
              </button>
            </form>
          )}
        </section>
      ) : null}

      {!activeFeature && !adminDraft ? (
        <FeatureIntro
          description="Choisissez une fonctionnalité dans les accès rapides pour administrer les comptes, institutions, accès, intégrations ou paramètres."
          icon={<ServerCog size={22} />}
          title="Console prête"
        />
      ) : null}

      {activeFeature === "admin-institutions" ? (
      <section className="settings-panel" id="admin-institutions-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Institutions</h2>
            <p>Organismes autorisés à échanger des demandes et documents</p>
          </div>
          <button className="ghost-button" onClick={() => onOpenAdminDraft("institution")} type="button">
            <Building2 size={17} />
            Nouvelle institution
          </button>
        </div>

        <div className="user-list">
          {institutions.length ? (
            institutions.map((institution) => (
              <div className="user-row" key={institution.id}>
                <span>{institution.code.slice(0, 2).toUpperCase()}</span>
                <div>
                  <strong>{institution.name}</strong>
                  <p>
                    {institution.code} · {formatInstitutionType(institution.type)}
                  </p>
                </div>
                <StatusPill label={institution.status === "ACTIVE" ? "Active" : institution.status} />
                <small>{institution.type}</small>
              </div>
            ))
          ) : (
            <p className="empty-state">Aucune institution enregistrée.</p>
          )}
        </div>
      </section>
      ) : null}

      {activeFeature === "admin-users" ? (
      <section className="settings-panel" id="admin-users-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Utilisateurs</h2>
            <p>Comptes enregistrés et profils d'accès</p>
          </div>
          <button className="ghost-button" onClick={() => onOpenAdminDraft("user")} type="button">
            <Users size={17} />
            Nouveau compte
          </button>
        </div>

        <div className="user-list">
          {users.length ? (
            users.map((user) => (
              <div className="user-row" key={user.id}>
                <span>{initials(user.full_name)}</span>
                <div>
                  <strong>{user.full_name}</strong>
                  <p>{user.email}</p>
                </div>
                <StatusPill label={formatRole(user.role)} />
                <small>{user.status}</small>
              </div>
            ))
          ) : (
            <p className="empty-state">Aucun utilisateur chargé.</p>
          )}
        </div>
      </section>
      ) : null}

      {activeFeature === "admin-governance" || activeFeature === "access" ? (
      <section className="settings-panel" id="admin-governance-panel">
        <div className="panel-toolbar">
          <div>
            <h2>{activeFeature === "access" ? "Authentification et accès" : "Paramètres de gouvernance"}</h2>
            <p>Configuration visible par les administrateurs de la plateforme</p>
          </div>
          <button className="ghost-button" type="button">
            <Settings size={17} />
            Modifier
          </button>
        </div>

        <div className="settings-list">
          <SettingRow label="Validation MFA obligatoire" value="Activée" tone="success" />
          <SettingRow label="Durée de session administrateur" value="15 min" />
          <SettingRow label="Institutions enregistrées" value={String(dashboard.institutions)} />
          <SettingRow label="Événements sécurité" value={String(dashboard.security_events)} tone="warning" />
        </div>
      </section>
      ) : null}

      {activeFeature === "integrations" || activeFeature === "backup" || activeFeature === "audit" || activeFeature === "notifications" ? (
        <CapabilityPanel feature={activeFeature} />
      ) : null}
    </section>
  );
}

function DocumentsWorkspace({
  activeFeature,
  attachmentsByCase,
  currentUser,
  exchangeCases,
  institutions,
  onAssignCase,
  onCreateCase,
  onDraftResponse,
  onUploadAttachment,
  onValidateResponse,
  onWorkflowAction,
  onWorkflowDraftCancel,
  onWorkflowDraftSubmit,
  users,
  workflowDraft,
}: {
  activeFeature: FeatureKey | null;
  attachmentsByCase: Record<string, Attachment[]>;
  currentUser: AuthUser | null;
  exchangeCases: ExchangeCase[];
  institutions: Institution[];
  onAssignCase: (caseId: string, assignedTo: string) => void;
  onCreateCase: (event: FormEvent<HTMLFormElement>) => void;
  onDraftResponse: (caseId: string) => void;
  onUploadAttachment: (event: FormEvent<HTMLFormElement>) => void;
  onValidateResponse: (caseId: string, approved: boolean) => void;
  onWorkflowAction: (caseId: string, action: "send" | "receive" | "send-response" | "close") => void;
  onWorkflowDraftCancel: () => void;
  onWorkflowDraftSubmit: (event: FormEvent<HTMLFormElement>) => void;
  users: PlatformUser[];
  workflowDraft: WorkflowDraft;
}) {
  const currentInstitution = institutions.find((institution) => institution.id === currentUser?.institution_id);
  const receivers = institutions.filter((institution) => institution.id !== currentUser?.institution_id);
  const availableReceivers = receivers.length ? receivers : institutions;
  const listFeatures: Array<FeatureKey | null> = [
    "cases",
    "secure-transmission",
    "receive-assign",
    "processing",
    "validation",
    "secure-response",
    "lifecycle",
    "classification",
  ];
  const shouldShowCases = listFeatures.includes(activeFeature);
  const filteredCases = getCasesForFeature(exchangeCases, activeFeature, currentUser?.id ?? null);
  const classificationStats = getClassificationStats(exchangeCases);
  const accessRows = currentUser
    ? [
        { label: "Identité", value: currentUser.full_name },
        { label: "Adresse institutionnelle", value: currentUser.email },
        { label: "Rôle", value: formatRole(currentUser.role) },
        { label: "Institution", value: currentInstitution?.name ?? "Institution non chargée" },
      ]
    : [];

  return (
    <section className="documents-layout">
      {!activeFeature ? (
        <FeatureIntro
          description="Sélectionnez un accès rapide pour créer une demande, téléverser une pièce, traiter un dossier ou consulter le cycle de vie."
          icon={<Workflow size={22} />}
          title="Espace documents"
        />
      ) : null}

      {activeFeature === "access" ? (
      <section className="settings-panel" id="core-access-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Authentification et accès</h2>
            <p>Profil connecté, périmètre institutionnel et droits applicatifs</p>
          </div>
          <StatusPill label={currentUser ? formatRole(currentUser.role) : "Observateur"} />
        </div>
        <div className="core-summary-grid">
          <article>
            <KeyRound size={20} />
            <strong>Session active</strong>
            <span>Jeton API authentifié</span>
          </article>
          <article>
            <Building2 size={20} />
            <strong>{currentInstitution?.code ?? "Institution"}</strong>
            <span>{currentInstitution?.name ?? "Périmètre du compte"}</span>
          </article>
          <article>
            <ShieldCheck size={20} />
            <strong>{currentUser ? formatRole(currentUser.role) : "Profil"}</strong>
            <span>{isAdminRole(currentUser?.role ?? "OBSERVER") ? "Administration autorisée" : "Accès métier contrôlé"}</span>
          </article>
        </div>
        <div className="settings-list">
          {accessRows.map((row) => (
            <SettingRow key={row.label} label={row.label} value={row.value} />
          ))}
        </div>
      </section>
      ) : null}

      {activeFeature === "new-case" ? (
      <section className="request-form-panel" id="new-request-form">
        <div className="panel-toolbar">
          <div>
            <h2>Nouvelle demande d'information</h2>
            <p>{currentInstitution ? `Institution émettrice: ${currentInstitution.name}` : "Institution émettrice du compte connecté"}</p>
          </div>
        </div>

        <form className="request-form" onSubmit={onCreateCase}>
          <label>
            <span>Référence</span>
            <input name="reference" placeholder="IB-2026-0050" required />
          </label>
          <label>
            <span>Objet</span>
            <input name="subject" placeholder="Objet de la demande" required />
          </label>
          <label>
            <span>Institution destinataire</span>
            <select name="receiver_institution_id" required>
              <option value="">Sélectionner</option>
              {availableReceivers.map((institution) => (
                <option key={institution.id} value={institution.id}>
                  {institution.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Classification</span>
            <select name="classification">
              <option value="INTERNE">Interne</option>
              <option value="CONFIDENTIEL">Confidentiel</option>
              <option value="SECRET">Secret</option>
              <option value="PUBLIC">Public</option>
            </select>
          </label>
          <label>
            <span>Priorité</span>
            <select name="priority">
              <option value="NORMAL">Normale</option>
              <option value="HIGH">Haute</option>
              <option value="URGENT">Urgente</option>
              <option value="LOW">Basse</option>
            </select>
          </label>
          <label className="wide-field">
            <span>Description</span>
            <textarea name="description" placeholder="Contexte, informations demandées, contraintes de délai..." />
          </label>
          <label className="wide-field">
            <span>Pièce jointe initiale</span>
            <input name="file" type="file" />
          </label>
          <button className="primary-button" type="submit">
            <FilePlus2 size={18} />
            Créer la demande
          </button>
        </form>
      </section>
      ) : null}

      {activeFeature === "upload-document" ? (
      <section className="request-form-panel" id="upload-document-form">
        <div className="panel-toolbar">
          <div>
            <h2>Ajouter une pièce à un dossier</h2>
            <p>Le fichier est chiffré au stockage et journalisé.</p>
          </div>
        </div>
        <form className="request-form compact-form" onSubmit={onUploadAttachment}>
          <label>
            <span>Dossier</span>
            <select name="case_id" required>
              <option value="">Sélectionner</option>
              {exchangeCases.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.reference} - {item.subject}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Fichier</span>
            <input name="file" required type="file" />
          </label>
          <button className="primary-button" type="submit">
            <UploadCloud size={18} />
            Téléverser
          </button>
        </form>
      </section>
      ) : null}

      {activeFeature === "classification" ? (
      <section className="classification-panel" id="classification-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Classification de l'information</h2>
            <p>Répartition des demandes par niveau de sensibilité</p>
          </div>
        </div>
        <div className="classification-grid">
          {classificationStats.map((item) => (
            <article key={item.level}>
              <StatusPill label={formatClassification(item.level)} />
              <strong>{item.count}</strong>
              <span>{item.description}</span>
            </article>
          ))}
        </div>
      </section>
      ) : null}

      {shouldShowCases ? (
      <section className="document-panel" id="cases-list-panel">
        <div className="panel-toolbar">
          <div>
            <h2>{activeFeature ? getFeatureTitle(activeFeature) : "Dossiers et documents"}</h2>
            <p>{getFeatureDescription(activeFeature)}</p>
          </div>
          <button aria-label="Options documents" className="icon-button" type="button">
            <MoreHorizontal size={18} />
          </button>
        </div>

        {workflowDraft ? (
          <form className="workflow-draft-panel" onSubmit={onWorkflowDraftSubmit}>
            <div>
              <h3>{workflowDraft.title}</h3>
              <p>
                {workflowDraft.mode === "response"
                  ? "Rédigez la réponse proposée avant validation hiérarchique."
                  : workflowDraft.approved
                    ? "Ajoutez le commentaire de validation."
                    : "Indiquez le motif du rejet."}
              </p>
            </div>
            <textarea
              name="body"
              placeholder={workflowDraft.mode === "response" ? "Réponse proposée..." : "Commentaire..."}
              required
            />
            <div className="workflow-draft-actions">
              <button className="ghost-button" onClick={onWorkflowDraftCancel} type="button">
                Annuler
              </button>
              <button className="primary-button" type="submit">
                Confirmer
              </button>
            </div>
          </form>
        ) : null}

        <div className="document-list">
          {filteredCases.length ? (
            filteredCases.map((item) => {
              const caseAttachments = attachmentsByCase[item.id] ?? [];
              const sender = institutions.find((institution) => institution.id === item.sender_institution_id);
              const receiver = institutions.find((institution) => institution.id === item.receiver_institution_id);
              const canAssign = users.length > 0 && ["RECEIVED", "SENT", "IN_REVIEW"].includes(item.status);

              return (
                <article className="document-row" key={item.id}>
                  <div className="document-icon">
                    <FileText size={21} />
                  </div>
                  <div className="document-main">
                    <strong>{item.subject}</strong>
                    <p>
                      {item.reference} · {sender?.name ?? "Institution"} vers {receiver?.name ?? "Institution"}
                    </p>
                    {caseAttachments.length ? (
                      <small>{caseAttachments.map((attachment) => attachment.file_name).join(", ")}</small>
                    ) : null}
                  </div>
                  <span className="document-type">{formatStatus(item.status)}</span>
                  <span className="document-date">{formatDate(item.created_at)}</span>
                  <span className="document-size">{caseAttachments.length} pièce(s)</span>
                  <StatusPill label={formatClassification(item.classification)} />
                  <button className="icon-button" type="button" aria-label={`Consulter ${item.reference}`}>
                    <Download size={18} />
                  </button>
                  <div className="workflow-actions">
                    {item.status === "DRAFT" ? (
                      <button className="ghost-button" onClick={() => onWorkflowAction(item.id, "send")} type="button">
                        Transmettre
                      </button>
                    ) : null}
                    {item.status === "SENT" ? (
                      <button className="ghost-button" onClick={() => onWorkflowAction(item.id, "receive")} type="button">
                        Réceptionner
                      </button>
                    ) : null}
                    {canAssign ? (
                      <select onChange={(event) => onAssignCase(item.id, event.target.value)} defaultValue="">
                        <option value="">Affecter</option>
                        {users.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.full_name}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    {["ASSIGNED", "IN_PROGRESS", "RECEIVED"].includes(item.status) ? (
                      <button className="ghost-button" onClick={() => onDraftResponse(item.id)} type="button">
                        Répondre
                      </button>
                    ) : null}
                    {item.status === "PENDING_VALIDATION" ? (
                      <>
                        <button className="ghost-button" onClick={() => onValidateResponse(item.id, true)} type="button">
                          Valider
                        </button>
                        <button className="ghost-button" onClick={() => onValidateResponse(item.id, false)} type="button">
                          Rejeter
                        </button>
                      </>
                    ) : null}
                    {item.status === "APPROVED" ? (
                      <button className="ghost-button" onClick={() => onWorkflowAction(item.id, "send-response")} type="button">
                        Envoyer réponse
                      </button>
                    ) : null}
                    {item.status === "RESPONSE_SENT" ? (
                      <button className="ghost-button" onClick={() => onWorkflowAction(item.id, "close")} type="button">
                        Clôturer
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })
          ) : (
            <p className="empty-state">Aucune demande ne correspond à cette vue.</p>
          )}
        </div>
      </section>
      ) : null}

      {activeFeature &&
      !shouldShowCases &&
      activeFeature !== "access" &&
      activeFeature !== "new-case" &&
      activeFeature !== "upload-document" ? (
        <CapabilityPanel feature={activeFeature} />
      ) : null}
    </section>
  );
}

function CaseQueue() {
  return (
    <div className="case-panel">
      <div className="panel-toolbar">
        <div>
          <h2>File de traitement</h2>
          <p>Dossiers récents classés par priorité opérationnelle</p>
        </div>
        <div className="toolbar-actions">
          <button className="ghost-button" type="button">
            <SlidersHorizontal size={17} />
            Filtres
          </button>
          <button aria-label="Options" className="icon-button" type="button">
            <MoreHorizontal size={18} />
          </button>
        </div>
      </div>

      <div className="table-header" aria-hidden="true">
        <span>Dossier</span>
        <span>Flux</span>
        <span>Responsable</span>
        <span>Échéance</span>
      </div>

      <div className="case-list">
        {cases.map((item) => (
          <article className="case-row" key={item.reference}>
            <div className="case-main">
              <div className="case-title">
                <strong>{item.reference}</strong>
                <StatusBadge status={item.status} />
              </div>
              <p>{item.subject}</p>
              <div className="classification">
                <LockKeyhole size={13} />
                {item.classification}
              </div>
            </div>

            <div className="route">
              <span>{item.sender}</span>
              <ArrowUpRight size={15} />
              <span>{item.receiver}</span>
            </div>

            <div className="owner">
              <span>{initials(item.owner)}</span>
              <strong>{item.owner}</strong>
            </div>

            <div className="deadline">
              <span>{item.due}</span>
              <div className="progress-track">
                <span style={{ width: `${item.progress}%` }} />
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function InsightRail() {
  return (
    <aside className="insight-rail" aria-label="Contrôle sécurité">
      <section className="security-card">
        <div className="security-score">
          <Fingerprint size={24} />
          <strong>98</strong>
        </div>
        <h2>Confiance réseau</h2>
        <p>Contrôles d'accès, signatures et pièces jointes restent dans le seuil attendu.</p>
        <button className="secondary-button" type="button">
          Rapport sécurité
          <ChevronDown size={16} />
        </button>
      </section>

      <section className="rail-section">
        <div className="rail-heading">
          <h2>Journal récent</h2>
          <span>Temps réel</span>
        </div>
        <div className="audit-list">
          {auditTrail.map((item) => (
            <div className="audit-item" key={`${item.label}-${item.detail}`}>
              <span className={`audit-icon ${item.tone}`}>
                {item.tone === "success" ? <CheckCircle2 size={16} /> : <Clock3 size={16} />}
              </span>
              <div>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rail-section compact">
        <div>
          <Inbox size={18} />
          <span>Messages à traiter</span>
        </div>
        <strong>12</strong>
      </section>

      <section className="rail-section compact">
        <div>
          <MessageSquareText size={18} />
          <span>Demandes de validation</span>
        </div>
        <strong>5</strong>
      </section>
    </aside>
  );
}

function MetricCard({ icon, label, value, delta }: { icon: ReactNode; label: string; value: number; delta: string }) {
  return (
    <article className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value.toLocaleString("fr-FR")}</strong>
      </div>
      <p>{delta}</p>
    </article>
  );
}

function SettingRow({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "success" | "warning" }) {
  return (
    <div className="setting-row">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function StatusPill({ label }: { label: string }) {
  const tone: Record<string, string> = {
    Interne: "received",
    Confidentiel: "review",
    Secret: "urgent",
    Public: "approved",
    "Admin système": "urgent",
    "Admin institution": "review",
    Agent: "approved",
    Validateur: "review",
    Observateur: "received",
    Auditeur: "urgent",
    Active: "approved",
  };

  return <span className={`status-badge ${tone[label] ?? "received"}`}>{label}</span>;
}

function StatusBadge({ status }: { status: CaseItem["status"] }) {
  const statusClass: Record<CaseItem["status"], string> = {
    "En revue": "review",
    Reçu: "received",
    Approuvé: "approved",
    Urgent: "urgent",
  };

  return <span className={`status-badge ${statusClass[status]}`}>{status}</span>;
}

function getSectionTitle(section: AppSection) {
  const titles: Record<AppSection, string> = {
    overview: "Centre de coordination",
    admin: "Administration de la plateforme",
    documents: "Consultation des documents",
  };

  return titles[section];
}

function getVisibleNavItems(role: UserRole) {
  if (role === "admin") {
    return navItems;
  }

  return navItems.filter((item) => item.id === "documents");
}

function isAdminRole(role: AuthUser["role"]) {
  return role === "SYSTEM_ADMIN" || role === "INSTITUTION_ADMIN";
}

function formatClassification(classification: string) {
  const labels: Record<string, string> = {
    CONFIDENTIEL: "Confidentiel",
    INTERNE: "Interne",
    PUBLIC: "Public",
    SECRET: "Secret",
  };

  return labels[classification] ?? classification;
}

function formatRole(role: AuthUser["role"]) {
  const labels: Record<AuthUser["role"], string> = {
    AGENT: "Agent",
    AUDITOR: "Auditeur",
    INSTITUTION_ADMIN: "Admin institution",
    OBSERVER: "Observateur",
    SYSTEM_ADMIN: "Admin système",
    VALIDATOR: "Validateur",
  };

  return labels[role];
}

function formatInstitutionType(type: string) {
  const labels: Record<string, string> = {
    AGENCY: "Agence",
    BANK: "Banque",
    COMMUNE: "Commune",
    MINISTRY: "Ministère",
    OPERATOR: "Opérateur",
    OTHER: "Autre",
    PRIVATE: "Privé",
  };

  return labels[type] ?? type;
}

function formatStatus(status: string) {
  const labels: Record<string, string> = {
    APPROVED: "Validée",
    ARCHIVED: "Archivée",
    ASSIGNED: "Affectée",
    CLOSED: "Clôturée",
    DRAFT: "Brouillon",
    IN_PROGRESS: "Traitement",
    IN_REVIEW: "En revue",
    PENDING_VALIDATION: "Validation",
    RECEIVED: "Reçue",
    REJECTED: "Rejetée",
    RESPONSE_SENT: "Réponse envoyée",
    SENT: "Transmise",
  };

  return labels[status] ?? status;
}

function getCasesForFeature(items: ExchangeCase[], feature: FeatureKey | null, currentUserId: string | null) {
  if (feature === "secure-transmission") {
    return items.filter((item) => ["DRAFT", "SENT"].includes(item.status));
  }

  if (feature === "receive-assign") {
    return items.filter((item) => ["SENT", "RECEIVED", "ASSIGNED"].includes(item.status));
  }

  if (feature === "processing") {
    return items.filter(
      (item) =>
        ["ASSIGNED", "IN_PROGRESS", "RECEIVED", "REJECTED"].includes(item.status) &&
        (!currentUserId || !item.assigned_to || item.assigned_to === currentUserId),
    );
  }

  if (feature === "validation") {
    return items.filter((item) => item.status === "PENDING_VALIDATION");
  }

  if (feature === "secure-response") {
    return items.filter((item) => ["APPROVED", "RESPONSE_SENT"].includes(item.status));
  }

  if (feature === "lifecycle") {
    return [...items].sort((first, second) => getLifecycleRank(first.status) - getLifecycleRank(second.status));
  }

  if (feature === "classification") {
    return [...items].sort((first, second) => getClassificationRank(second.classification) - getClassificationRank(first.classification));
  }

  return items;
}

function getClassificationStats(items: ExchangeCase[]) {
  const descriptions: Record<string, string> = {
    CONFIDENTIEL: "Accès restreint",
    INTERNE: "Usage institutionnel",
    PUBLIC: "Diffusion ouverte",
    SECRET: "Traitement renforcé",
  };

  return ["PUBLIC", "INTERNE", "CONFIDENTIEL", "SECRET"].map((level) => ({
    count: items.filter((item) => item.classification === level).length,
    description: descriptions[level],
    level,
  }));
}

function getClassificationRank(classification: string) {
  const ranks: Record<string, number> = {
    CONFIDENTIEL: 3,
    INTERNE: 2,
    PUBLIC: 1,
    SECRET: 4,
  };

  return ranks[classification] ?? 0;
}

function getLifecycleRank(status: string) {
  const ranks: Record<string, number> = {
    APPROVED: 9,
    ARCHIVED: 12,
    ASSIGNED: 4,
    CLOSED: 11,
    DRAFT: 1,
    IN_PROGRESS: 6,
    IN_REVIEW: 5,
    PENDING_VALIDATION: 7,
    RECEIVED: 3,
    REJECTED: 8,
    RESPONSE_SENT: 10,
    SENT: 2,
  };

  return ranks[status] ?? 99;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short" }).format(new Date(value));
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
