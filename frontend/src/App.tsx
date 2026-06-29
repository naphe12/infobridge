import { AlertTriangle, Archive, Building2, FileCheck2, LockKeyhole, ShieldCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

type Dashboard = {
  institutions: number;
  users: number;
  cases: number;
  security_events: number;
};

const cases = [
  {
    reference: "IB-2026-0001",
    subject: "Demande de vérification d'identité institutionnelle",
    sender: "Ministère des Finances",
    receiver: "Banque Centrale",
    status: "IN_REVIEW",
    classification: "CONFIDENTIEL",
  },
  {
    reference: "IB-2026-0002",
    subject: "Transmission de pièces justificatives",
    sender: "Commune de Bujumbura",
    receiver: "Agence Nationale",
    status: "RECEIVED",
    classification: "INTERNE",
  },
];

export function App() {
  const [dashboard, setDashboard] = useState<Dashboard>({
    institutions: 0,
    users: 0,
    cases: 0,
    security_events: 0,
  });

  useEffect(() => {
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
  }, []);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={30} />
          <span>InfoBridge</span>
        </div>
        <nav>
          <a className="active" href="/">
            <FileCheck2 size={18} />
            Dossiers
          </a>
          <a href="/">
            <Building2 size={18} />
            Institutions
          </a>
          <a href="/">
            <Users size={18} />
            Utilisateurs
          </a>
          <a href="/">
            <Archive size={18} />
            Audit
          </a>
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Guichet sécurisé inter-institutions</p>
            <h1>Dossiers d'échange</h1>
          </div>
          <button className="primary-button" type="button">
            Nouveau dossier
          </button>
        </header>

        <section className="metrics" aria-label="Indicateurs">
          <Metric icon={<Building2 size={22} />} label="Institutions" value={String(dashboard.institutions)} />
          <Metric icon={<FileCheck2 size={22} />} label="Dossiers actifs" value={String(dashboard.cases)} />
          <Metric icon={<LockKeyhole size={22} />} label="Confidentiels" value="0" />
          <Metric icon={<AlertTriangle size={22} />} label="Alertes sécurité" value={String(dashboard.security_events)} />
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>Activité récente</h2>
            <span>Prototype MVP</span>
          </div>
          <div className="case-list">
            {cases.map((item) => (
              <article className="case-row" key={item.reference}>
                <div>
                  <strong>{item.reference}</strong>
                  <p>{item.subject}</p>
                </div>
                <div className="route">
                  {item.sender}
                  <span>vers</span>
                  {item.receiver}
                </div>
                <span className="badge">{item.status}</span>
                <span className="badge muted">{item.classification}</span>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <article className="metric">
      {icon}
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}
