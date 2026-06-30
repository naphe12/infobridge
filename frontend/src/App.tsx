import {
  AlertTriangle,
  Archive,
  ArrowUpRight,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Database,
  Download,
  Eye,
  EyeOff,
  FileCheck2,
  FileText,
  FilePlus2,
  Fingerprint,
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
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  Users,
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

const adminModules = [
  {
    icon: Building2,
    title: "Institutions",
    description: "Créer, suspendre et vérifier les organismes connectés.",
    value: "12 actives",
  },
  {
    icon: Users,
    title: "Utilisateurs et rôles",
    description: "Attribuer les profils administrateur, agent et observateur.",
    value: "48 comptes",
  },
  {
    icon: KeyRound,
    title: "Sécurité d'accès",
    description: "Suivre MFA, verrouillages et politiques de session.",
    value: "92% MFA",
  },
  {
    icon: Database,
    title: "Référentiels",
    description: "Administrer classifications, statuts et paramètres métier.",
    value: "9 listes",
  },
];

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
      setAppMessage("Pièce jointe chiffrée téléversée.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Téléversement impossible.");
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

  async function handleDraftResponse(caseId: string) {
    const responseBody = window.prompt("Réponse proposée");
    if (!responseBody) {
      return;
    }

    try {
      await apiFetch<ExchangeCase>(`/cases/${caseId}/response`, {
        body: JSON.stringify({ response_body: responseBody }),
        method: "POST",
      });
      setAppMessage("Réponse envoyée en validation.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Rédaction impossible.");
    }
  }

  async function handleValidateResponse(caseId: string, approved: boolean) {
    const comment = window.prompt(approved ? "Commentaire de validation" : "Motif du rejet") ?? "";

    try {
      await apiFetch<ExchangeCase>(`/cases/${caseId}/validate`, {
        body: JSON.stringify({ approved, comment }),
        method: "POST",
      });
      setAppMessage(approved ? "Réponse validée." : "Réponse rejetée.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Validation impossible.");
    }
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
                onClick={() => setActiveSection(item.id)}
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
            <button className="primary-button" type="button">
              {activeSection === "documents" ? <UploadCloud size={18} /> : <FilePlus2 size={18} />}
              {activeSection === "documents" ? "Déposer un document" : "Nouveau dossier"}
            </button>
          </div>
        </header>

        {activeSection === "overview" ? <Overview metrics={metrics} /> : null}
        {appMessage ? <p className="app-message">{appMessage}</p> : null}
        {activeSection === "admin" ? (
          <AdminWorkspace dashboard={dashboard} institutions={institutions} users={users} />
        ) : null}
        {activeSection === "documents" ? (
          <DocumentsWorkspace
            attachmentsByCase={attachmentsByCase}
            currentUser={currentUser}
            exchangeCases={exchangeCases}
            institutions={institutions}
            onAssignCase={handleAssignCase}
            onCreateCase={handleCreateCase}
            onDraftResponse={handleDraftResponse}
            onUploadAttachment={handleUploadAttachment}
            onValidateResponse={handleValidateResponse}
            onWorkflowAction={handleWorkflowAction}
            users={users}
          />
        ) : null}
      </section>
    </main>
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
  dashboard,
  institutions,
  users,
}: {
  dashboard: Dashboard;
  institutions: Institution[];
  users: PlatformUser[];
}) {
  const moduleValues: Record<string, string> = {
    Institutions: `${institutions.length || dashboard.institutions} actives`,
    "Utilisateurs et rôles": `${users.length || dashboard.users} comptes`,
    "Sécurité d'accès": "MFA disponible",
    Référentiels: "Classifications",
  };

  return (
    <section className="admin-layout">
      <div className="admin-hero">
        <div>
          <span className="section-label">Administration plateforme</span>
          <h2>Pilotage des accès, institutions et paramètres</h2>
          <p>Centralisez les actions sensibles de gouvernance et gardez une visibilité immédiate sur l'état du système.</p>
        </div>
        <button className="primary-button" type="button">
          <Users size={18} />
          Inviter un utilisateur
        </button>
      </div>

      <section className="admin-grid" aria-label="Modules d'administration">
        {adminModules.map((module) => {
          const Icon = module.icon;
          return (
            <article className="admin-module" key={module.title}>
              <div className="admin-module-icon">
                <Icon size={21} />
              </div>
              <strong>{module.title}</strong>
              <p>{module.description}</p>
              <span>{moduleValues[module.title] ?? module.value}</span>
            </article>
          );
        })}
      </section>

      <section className="settings-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Utilisateurs</h2>
            <p>Comptes enregistrés et profils d'accès</p>
          </div>
          <button className="ghost-button" type="button">
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

      <section className="settings-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Paramètres de gouvernance</h2>
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
    </section>
  );
}

function DocumentsWorkspace({
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
  users,
}: {
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
  users: PlatformUser[];
}) {
  const currentInstitution = institutions.find((institution) => institution.id === currentUser?.institution_id);
  const receivers = institutions.filter((institution) => institution.id !== currentUser?.institution_id);
  const availableReceivers = receivers.length ? receivers : institutions;

  return (
    <section className="documents-layout">
      <section className="request-form-panel">
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

      <section className="request-form-panel">
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

      <section className="document-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Dossiers et documents</h2>
            <p>Accès contrôlé aux demandes et pièces téléversées</p>
          </div>
          <button aria-label="Options documents" className="icon-button" type="button">
            <MoreHorizontal size={18} />
          </button>
        </div>

        <div className="document-list">
          {exchangeCases.length ? (
            exchangeCases.map((item) => {
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
            <p className="empty-state">Aucune demande disponible pour ce profil.</p>
          )}
        </div>
      </section>
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
