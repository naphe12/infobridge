import {
  AlertTriangle,
  Archive,
  ArrowUpRight,
  Bell,
  Building2,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Eye,
  EyeOff,
  FileCheck2,
  FilePlus2,
  Fingerprint,
  Inbox,
  LayoutDashboard,
  LockKeyhole,
  LogIn,
  LogOut,
  Mail,
  MessageSquareText,
  MoreHorizontal,
  Search,
  ShieldCheck,
  SlidersHorizontal,
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
  { label: "Vue d'ensemble", icon: LayoutDashboard, active: true },
  { label: "Dossiers", icon: FileCheck2 },
  { label: "Institutions", icon: Building2 },
  { label: "Utilisateurs", icon: Users },
  { label: "Audit", icon: Archive },
];

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => sessionStorage.getItem("infobridge_session") === "active");
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

    fetch(`${apiUrl}/dashboard`)
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
  }, [isAuthenticated]);

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

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    if (!email || !password) {
      setLoginError("Renseignez votre adresse e-mail et votre mot de passe.");
      return;
    }

    sessionStorage.setItem("infobridge_session", "active");
    setLoginError("");
    setIsAuthenticated(true);
  }

  function handleLogout() {
    sessionStorage.removeItem("infobridge_session");
    setIsAuthenticated(false);
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
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <a className={item.active ? "active" : undefined} href="/" key={item.label}>
                <Icon size={18} />
                <span>{item.label}</span>
              </a>
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
            <span className="section-label">Guichet sécurisé</span>
            <h1>Centre de coordination</h1>
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
              <FilePlus2 size={18} />
              Nouveau dossier
            </button>
            <button className="icon-button" onClick={handleLogout} type="button" aria-label="Se déconnecter">
              <LogOut size={18} />
            </button>
          </div>
        </header>

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
        </section>
      </section>
    </main>
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

function StatusBadge({ status }: { status: CaseItem["status"] }) {
  const statusClass: Record<CaseItem["status"], string> = {
    "En revue": "review",
    Reçu: "received",
    Approuvé: "approved",
    Urgent: "urgent",
  };

  return <span className={`status-badge ${statusClass[status]}`}>{status}</span>;
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
