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

type DocumentItem = {
  title: string;
  reference: string;
  institution: string;
  classification: "Interne" | "Confidentiel" | "Secret";
  type: string;
  updatedAt: string;
  size: string;
};

const documents: DocumentItem[] = [
  {
    title: "Décision de validation institutionnelle",
    reference: "DOC-2026-118",
    institution: "Banque Centrale",
    classification: "Confidentiel",
    type: "PDF signé",
    updatedAt: "29/06/2026",
    size: "1.8 Mo",
  },
  {
    title: "Pièces justificatives consolidées",
    reference: "DOC-2026-117",
    institution: "Commune de Bujumbura",
    classification: "Interne",
    type: "Archive ZIP",
    updatedAt: "28/06/2026",
    size: "8.4 Mo",
  },
  {
    title: "Rapport de rapprochement documentaire",
    reference: "DOC-2026-116",
    institution: "Ministère de la Justice",
    classification: "Secret",
    type: "PDF chiffré",
    updatedAt: "27/06/2026",
    size: "2.2 Mo",
  },
];

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

    fetch(`${apiUrl}/dashboard`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Dashboard request failed");
        }
        return response.json() as Promise<Dashboard>;
      })
      .then(setDashboard)
      .catch(() => {
        setDashboard({
          institutions: 0,
          users: 0,
          cases: 0,
          security_events: 0,
        });
      });
  }, [accessToken, isAuthenticated]);

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
        throw new Error("Login failed");
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
    } catch {
      setLoginError("Connexion impossible. Vérifiez vos identifiants ou la disponibilité de l'API.");
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
            <button className="icon-button" onClick={handleLogout} type="button" aria-label="Se déconnecter">
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {activeSection === "overview" ? <Overview metrics={metrics} /> : null}
        {activeSection === "admin" ? <AdminWorkspace dashboard={dashboard} /> : null}
        {activeSection === "documents" ? <DocumentsWorkspace /> : null}
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

function AdminWorkspace({ dashboard }: { dashboard: Dashboard }) {
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
              <span>{module.value}</span>
            </article>
          );
        })}
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

function DocumentsWorkspace() {
  return (
    <section className="documents-layout">
      <div className="document-tools">
        <label className="document-search">
          <Search size={18} />
          <input aria-label="Rechercher un document" placeholder="Référence, titre, institution..." type="search" />
        </label>
        <button className="ghost-button" type="button">
          <SlidersHorizontal size={17} />
          Classifications
        </button>
        <button className="primary-button" type="button">
          <UploadCloud size={18} />
          Déposer
        </button>
      </div>

      <section className="document-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Consultation documentaire</h2>
            <p>Accès contrôlé aux documents transmis et validés</p>
          </div>
          <button aria-label="Options documents" className="icon-button" type="button">
            <MoreHorizontal size={18} />
          </button>
        </div>

        <div className="document-list">
          {documents.map((document) => (
            <article className="document-row" key={document.reference}>
              <div className="document-icon">
                <FileText size={21} />
              </div>
              <div className="document-main">
                <strong>{document.title}</strong>
                <p>
                  {document.reference} · {document.institution}
                </p>
              </div>
              <span className="document-type">{document.type}</span>
              <span className="document-date">{document.updatedAt}</span>
              <span className="document-size">{document.size}</span>
              <StatusPill label={document.classification} />
              <button className="icon-button" type="button" aria-label={`Télécharger ${document.title}`}>
                <Download size={18} />
              </button>
            </article>
          ))}
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

function StatusPill({ label }: { label: DocumentItem["classification"] }) {
  const tone: Record<DocumentItem["classification"], string> = {
    Interne: "received",
    Confidentiel: "review",
    Secret: "urgent",
  };

  return <span className={`status-badge ${tone[label]}`}>{label}</span>;
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

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
