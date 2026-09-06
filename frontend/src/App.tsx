import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpRight,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ClipboardCheck,
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
  Pencil,
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
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

type Dashboard = {
  institutions: number;
  users: number;
  cases: number;
  security_events: number;
  closed_cases?: number;
  response_rate?: number;
  overdue_cases?: number;
  due_soon_cases?: number;
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
type UserRole = "admin" | "auditor" | "user";
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
  | "admin-references"
  | "integrations";

type AuthUser = {
  id: string;
  institution_id: string;
  full_name: string;
  email: string;
  role: "SYSTEM_ADMIN" | "INSTITUTION_ADMIN" | "AGENT" | "VALIDATOR" | "CONSULTANT" | "OBSERVER" | "AUDITOR";
};

type LoginResponse = {
  access_token: string;
  refresh_token: string;
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
  response_body: string | null;
  sender_institution_id: string;
  receiver_institution_id: string;
  status: string;
  priority: string;
  classification: string;
  assigned_to: string | null;
  due_at: string | null;
  closed_at: string | null;
  retention_until: string | null;
  created_at: string;
};

type Attachment = {
  id: string;
  case_id: string | null;
  file_name: string;
  storage_backend: string;
  mime_type: string;
  size_bytes: number;
  checksum: string;
  purpose: string;
  encrypted: boolean;
  logical_document_id: string;
  version: number;
  supersedes_id: string | null;
  uploaded_at: string;
};

type Receipt = {
  id: string;
  case_id: string;
  receiver_user_id: string;
  receiver_name: string;
  received_at: string;
  read_at: string | null;
};

type NotificationItem = {
  id: string;
  user_id: string | null;
  institution_id: string | null;
  case_id: string | null;
  title: string;
  body: string;
  level: string;
  read: boolean;
  created_at: string;
};

type AuditLogItem = {
  id: string;
  user_id: string | null;
  institution_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  ip_address: string | null;
  extra: Record<string, unknown>;
  created_at: string;
};

type SecurityEventItem = {
  id: string;
  user_id: string | null;
  institution_id: string | null;
  event_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

type LifecycleStatus = {
  enabled: boolean;
  due_alerts_enabled: boolean;
  interval_seconds: number;
  due_soon_hours: number;
  running: boolean;
  last_completed_at: string | null;
  last_error: string | null;
};

type PlatformSetting = {
  key: string;
  value: boolean | number;
  default_value: boolean | number;
  value_type: "boolean" | "integer";
  category: "SECURITY" | "RETENTION" | "AUTOMATION";
  label: string;
  description: string;
  minimum: number | null;
  maximum: number | null;
  source: "database" | "environment";
};

type ReferenceItem = {
  catalog: "institution_type" | "case_priority" | "classification" | "attachment_purpose";
  catalog_label: string;
  code: string;
  label: string;
  description: string | null;
  active: boolean;
  sort_order: number;
  required_active: boolean;
  source: "built_in" | "database";
};

type ApiScopeItem = {
  code: "cases:read" | "documents:read";
  label: string;
  description: string;
};

type ApiClientItem = {
  id: string;
  name: string;
  institution_id: string | null;
  client_key: string;
  scopes: ApiScopeItem["code"][];
  active: boolean;
  token_version: number;
  created_at: string;
  updated_at: string | null;
  secret_rotated_at: string | null;
  last_used_at: string | null;
};

type ApiClientCredential = ApiClientItem & { client_secret: string };

type WorkflowDraft =
  | { mode: "response"; caseId: string; title: string }
  | { mode: "validate"; caseId: string; title: string; approved: boolean }
  | null;

type AdminDraft = "institution" | "user" | { institution: Institution } | { user: PlatformUser } | null;

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

const navItems = [
  { id: "overview", label: "Vue d'ensemble", icon: LayoutDashboard },
  { id: "admin", label: "Administration", icon: Settings },
  { id: "documents", label: "Documents", icon: FileText },
] satisfies Array<{ id: AppSection; label: string; icon: typeof LayoutDashboard }>;

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => sessionStorage.getItem("infobridge_session") === "active");
  const [accessToken, setAccessToken] = useState(() => sessionStorage.getItem("infobridge_token") ?? "");
  const refreshPromiseRef = useRef<Promise<string> | null>(null);
  const [userRole, setUserRole] = useState<UserRole>(() =>
    sessionStorage.getItem("infobridge_role") === "admin"
      ? "admin"
      : sessionStorage.getItem("infobridge_role") === "auditor" ? "auditor" : "user",
  );
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => {
    const storedUser = sessionStorage.getItem("infobridge_user");
    return storedUser ? (JSON.parse(storedUser) as AuthUser) : null;
  });
  const [activeSection, setActiveSection] = useState<AppSection>(() =>
    sessionStorage.getItem("infobridge_role") === "admin" || sessionStorage.getItem("infobridge_role") === "auditor" ? "admin" : "documents",
  );
  const [loginError, setLoginError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [appMessage, setAppMessage] = useState("");
  const [loadError, setLoadError] = useState("");
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [assignees, setAssignees] = useState<PlatformUser[]>([]);
  const [exchangeCases, setExchangeCases] = useState<ExchangeCase[]>([]);
  const [attachmentsByCase, setAttachmentsByCase] = useState<Record<string, Attachment[]>>({});
  const [receiptsByCase, setReceiptsByCase] = useState<Record<string, Receipt[]>>({});
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [securityEvents, setSecurityEvents] = useState<SecurityEventItem[]>([]);
  const [lifecycleStatus, setLifecycleStatus] = useState<LifecycleStatus | null>(null);
  const [platformSettings, setPlatformSettings] = useState<PlatformSetting[]>([]);
  const [referenceItems, setReferenceItems] = useState<ReferenceItem[]>([]);
  const [apiClients, setApiClients] = useState<ApiClientItem[]>([]);
  const [apiScopes, setApiScopes] = useState<ApiScopeItem[]>([]);
  const [apiClientCredential, setApiClientCredential] = useState<ApiClientCredential | null>(null);
  const [notificationLevel, setNotificationLevel] = useState("ALL");
  const [caseSearch, setCaseSearch] = useState("");
  const [caseStatusFilter, setCaseStatusFilter] = useState("ALL");
  const [casePriorityFilter, setCasePriorityFilter] = useState("ALL");
  const [caseClassificationFilter, setCaseClassificationFilter] = useState("ALL");
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
    const performRequest = async (token: string) => {
      try {
        return await fetch(`${apiUrl}${path}`, {
          ...init,
          headers: {
            Authorization: `Bearer ${token}`,
            ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
            ...init.headers,
          },
        });
      } catch {
        throw new Error(`Impossible de joindre l’API pour ${path}. Vérifiez la connexion ou réessayez dans quelques instants.`);
      }
    };

    let response = await performRequest(accessToken);
    if (response.status === 401 && !path.startsWith("/auth/")) {
      const refreshedToken = await refreshAccessToken();
      response = await performRequest(refreshedToken);
    }

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new Error(`${path} : ${payload?.detail ?? `Erreur API ${response.status}`}`);
    }

    return (await response.json()) as T;
  }

  async function refreshAccessToken(): Promise<string> {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const refreshToken = sessionStorage.getItem("infobridge_refresh_token");
    if (!refreshToken) {
      clearLocalSession();
      throw new Error("Session expirée. Veuillez vous reconnecter.");
    }

    refreshPromiseRef.current = fetch(`${apiUrl}/auth/refresh`, {
      body: JSON.stringify({ refresh_token: refreshToken }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    })
      .then(async (response) => {
        if (!response.ok) {
          clearLocalSession();
          throw new Error("Session expirée. Veuillez vous reconnecter.");
        }
        const data = (await response.json()) as LoginResponse;
        sessionStorage.setItem("infobridge_token", data.access_token);
        sessionStorage.setItem("infobridge_refresh_token", data.refresh_token);
        setAccessToken(data.access_token);
        return data.access_token;
      })
      .finally(() => {
        refreshPromiseRef.current = null;
      });

    return refreshPromiseRef.current;
  }

  async function loadWorkspaceData() {
    try {
      const [dashboardData, caseData, institutionData, notificationData, loadedLifecycleStatus, loadedReferenceItems] = await Promise.all([
        apiFetch<Dashboard>("/dashboard"),
        apiFetch<ExchangeCase[]>("/cases"),
        apiFetch<Institution[]>("/institutions"),
        apiFetch<NotificationItem[]>("/notifications"),
        apiFetch<LifecycleStatus>("/operations/lifecycle-status"),
        apiFetch<ReferenceItem[]>("/reference-data"),
      ]);

      setDashboard(dashboardData);
      setExchangeCases(caseData);
      setInstitutions(institutionData);
      setNotifications(notificationData);
      setLifecycleStatus(loadedLifecycleStatus);
      setReferenceItems(loadedReferenceItems);

      setAssignees(await apiFetch<PlatformUser[]>("/users/assignees").catch(() => []));

      if (userRole === "admin") {
        const [loadedUsers, loadedSettings, loadedApiClients, loadedApiScopes] = await Promise.all([
          apiFetch<PlatformUser[]>("/users"),
          apiFetch<PlatformSetting[]>("/settings"),
          apiFetch<ApiClientItem[]>("/integrations/api-clients"),
          apiFetch<ApiScopeItem[]>("/integrations/scopes"),
        ]);
        setUsers(loadedUsers);
        setPlatformSettings(loadedSettings);
        setApiClients(loadedApiClients);
        setApiScopes(loadedApiScopes);
      }
      if (userRole === "admin" || userRole === "auditor") {
        const [loadedAuditLogs, loadedSecurityEvents] = await Promise.all([
          apiFetch<AuditLogItem[]>("/audit-logs?limit=200"),
          apiFetch<SecurityEventItem[]>("/security-events?limit=200"),
        ]);
        setAuditLogs(loadedAuditLogs);
        setSecurityEvents(loadedSecurityEvents);
      }

      const attachmentPairs = await Promise.all(
        caseData.map(async (item) => [item.id, await apiFetch<Attachment[]>(`/cases/${item.id}/attachments`)] as const),
      );
      setAttachmentsByCase(Object.fromEntries(attachmentPairs));
      const receiptPairs = await Promise.all(
        caseData.map(async (item) => [item.id, await apiFetch<Receipt[]>(`/cases/${item.id}/receipts`)] as const),
      );
      setReceiptsByCase(Object.fromEntries(receiptPairs));
      setLoadError("");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Impossible de charger les données.");
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
        delta: `${dashboard.overdue_cases ?? 0} en retard`,
      },
      {
        icon: Users,
        label: "Utilisateurs",
        value: dashboard.users,
        delta: `${dashboard.users} compte(s) recensé(s)`,
      },
      {
        icon: AlertTriangle,
        label: "Alertes sécurité",
        value: dashboard.security_events,
        delta: `${dashboard.due_soon_cases ?? 0} échéance proche`,
      },
    ],
    [dashboard],
  );
  const unreadNotificationCount = notifications.filter((notification) => !notification.read).length;

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
        const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null;
        if (response.status === 401) {
          setLoginError(
            errorPayload?.detail === "Inactive or unknown user"
              ? "Compte verrouillé ou désactivé. Contactez un administrateur."
              : errorPayload?.detail === "Inactive institution"
                ? "Votre institution est suspendue ou inactive. Contactez un administrateur."
                : "Identifiants incorrects.",
          );
          return;
        }

        setLoginError(errorPayload?.detail ?? `Erreur API ${response.status}.`);
        return;
      }

      const data = (await response.json()) as LoginResponse;
      const role: UserRole = isAdminRole(data.user.role) ? "admin" : data.user.role === "AUDITOR" ? "auditor" : "user";

      sessionStorage.setItem("infobridge_session", "active");
      sessionStorage.setItem("infobridge_token", data.access_token);
      sessionStorage.setItem("infobridge_refresh_token", data.refresh_token);
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
    const dueAt = String(formData.get("due_at") ?? "");
    const payload = {
      reference: String(formData.get("reference") ?? "").trim(),
      subject: String(formData.get("subject") ?? "").trim(),
      description: String(formData.get("description") ?? "").trim() || null,
      sender_institution_id: currentUser.institution_id,
      receiver_institution_id: String(formData.get("receiver_institution_id") ?? ""),
      priority: String(formData.get("priority") ?? "NORMAL"),
      classification: String(formData.get("classification") ?? "INTERNE"),
      due_at: dueAt ? new Date(dueAt).toISOString() : null,
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
      upload.append("purpose", String(formData.get("purpose") ?? "RESPONSE"));
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

  async function handleUserStatus(userId: string, status: string) {
    const user = users.find((item) => item.id === userId);
    if (status === "DISABLED" && !window.confirm(`Désactiver ${user?.full_name ?? "cet utilisateur"} et révoquer ses sessions ?`)) {
      return;
    }
    try {
      await apiFetch(`/users/${userId}`, { method: "PATCH", body: JSON.stringify({ status }) });
      setAppMessage("Statut utilisateur mis à jour et sessions révoquées si nécessaire.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du statut impossible.");
    }
  }

  async function handleUpdateUser(userId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = {
      email: String(formData.get("email") ?? "").trim(),
      full_name: String(formData.get("full_name") ?? "").trim(),
      institution_id: String(formData.get("institution_id") ?? ""),
      role: String(formData.get("role") ?? "AGENT"),
    };
    try {
      const user = await apiFetch<PlatformUser>(`/users/${userId}`, {
        body: JSON.stringify(payload),
        method: "PATCH",
      });
      setAdminDraft(null);
      setActiveFeature("admin-users");
      setAppMessage(`Utilisateur ${user.full_name} modifié.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification utilisateur impossible.");
    }
  }

  async function handleRevokeUserSessions(userId: string) {
    const user = users.find((item) => item.id === userId);
    if (!window.confirm(`Révoquer toutes les sessions de ${user?.full_name ?? "cet utilisateur"} ?`)) {
      return;
    }
    try {
      const result = await apiFetch<{ revoked_sessions: number }>(`/users/${userId}/sessions/revoke`, { method: "POST" });
      if (currentUser?.id === userId) {
        clearLocalSession();
        return;
      }
      setAppMessage(`${result.revoked_sessions} session(s) révoquée(s).`);
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Révocation des sessions impossible.");
    }
  }

  async function handleInstitutionStatus(institutionId: string, status: string) {
    const institution = institutions.find((item) => item.id === institutionId);
    if (status === "SUSPENDED" && !window.confirm(`Suspendre ${institution?.name ?? "cette institution"} et révoquer toutes ses sessions ?`)) {
      return;
    }
    try {
      await apiFetch(`/institutions/${institutionId}`, { method: "PATCH", body: JSON.stringify({ status }) });
      setAppMessage("Statut de l’institution mis à jour.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du statut impossible.");
    }
  }

  async function handleUpdateInstitution(institutionId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload = {
      code: String(formData.get("code") ?? "").trim(),
      name: String(formData.get("name") ?? "").trim(),
      type: String(formData.get("type") ?? "AGENCY"),
    };
    try {
      const institution = await apiFetch<Institution>(`/institutions/${institutionId}`, {
        body: JSON.stringify(payload),
        method: "PATCH",
      });
      setAdminDraft(null);
      setActiveFeature("admin-institutions");
      setAppMessage(`Institution ${institution.name} modifiée.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification institution impossible.");
    }
  }

  async function handleUpdatePlatformSetting(key: string, value: boolean | number) {
    try {
      const updated = await apiFetch<PlatformSetting>(`/settings/${key}`, {
        body: JSON.stringify({ value }),
        method: "PUT",
      });
      setPlatformSettings((current) => current.map((item) => item.key === key ? updated : item));
      setAppMessage(`Paramètre « ${updated.label} » enregistré.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du paramètre impossible.");
    }
  }

  async function handleUpdateReferenceItem(item: ReferenceItem, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      const updated = await apiFetch<ReferenceItem>(`/reference-data/${item.catalog}/${item.code}`, {
        body: JSON.stringify({
          label: String(formData.get("label") ?? "").trim(),
          description: String(formData.get("description") ?? "").trim() || null,
          active: String(formData.get("active") ?? "false") === "true",
          sort_order: Number(formData.get("sort_order") ?? 0),
        }),
        method: "PUT",
      });
      setReferenceItems((current) => current.map((candidate) =>
        candidate.catalog === updated.catalog && candidate.code === updated.code ? updated : candidate,
      ));
      setAppMessage(`Référentiel « ${updated.label} » enregistré.`);
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du référentiel impossible.");
    }
  }

  async function handleCreateApiClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      const created = await apiFetch<ApiClientCredential>("/integrations/api-clients", {
        body: JSON.stringify({
          name: String(formData.get("name") ?? "").trim(),
          institution_id: String(formData.get("institution_id") ?? "") || null,
          scopes: formData.getAll("scopes").map(String),
        }),
        method: "POST",
      });
      setApiClientCredential(created);
      event.currentTarget.reset();
      setAppMessage(`Client M2M « ${created.name} » créé.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Création du client M2M impossible.");
    }
  }

  async function handleUpdateApiClient(client: ApiClientItem, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      await apiFetch<ApiClientItem>(`/integrations/api-clients/${client.id}`, {
        body: JSON.stringify({
          name: String(formData.get("name") ?? "").trim(),
          scopes: formData.getAll("scopes").map(String),
        }),
        method: "PATCH",
      });
      setAppMessage(`Client M2M « ${client.name} » mis à jour. Les anciens jetons ont été invalidés si les scopes ont changé.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du client M2M impossible.");
    }
  }

  async function handleApiClientStatus(client: ApiClientItem) {
    const nextActive = !client.active;
    if (!nextActive && !window.confirm(`Suspendre le client M2M ${client.name} et invalider ses jetons ?`)) {
      return;
    }
    try {
      await apiFetch<ApiClientItem>(`/integrations/api-clients/${client.id}`, {
        body: JSON.stringify({ active: nextActive }),
        method: "PATCH",
      });
      setAppMessage(nextActive ? "Client M2M réactivé." : "Client M2M suspendu et jetons invalidés.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Modification du client M2M impossible.");
    }
  }

  async function handleRotateApiClientSecret(client: ApiClientItem) {
    if (!window.confirm(`Faire tourner le secret de ${client.name} ? Tous ses jetons actuels seront invalidés.`)) {
      return;
    }
    try {
      const credential = await apiFetch<ApiClientCredential>(`/integrations/api-clients/${client.id}/rotate-secret`, {
        method: "POST",
      });
      setApiClientCredential(credential);
      setAppMessage("Secret M2M renouvelé.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Rotation du secret impossible.");
    }
  }

  async function handleWorkflowAction(caseId: string, action: "send" | "receive" | "start" | "send-response" | "close") {
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

  async function handleReceipt(caseId: string, markRead: boolean) {
    try {
      await apiFetch<Receipt>(`/cases/${caseId}/receipts${markRead ? "/read" : ""}`, {
        method: markRead ? "PATCH" : "POST",
      });
      setAppMessage(markRead ? "Dossier marqué comme lu." : "Accusé de réception enregistré.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Mise à jour de l’accusé impossible.");
    }
  }

  async function handleArchiveCase(caseId: string) {
    try {
      await apiFetch<ExchangeCase>(`/cases/${caseId}/archive`, {
        body: JSON.stringify({}),
        method: "POST",
      });
      setAppMessage("Dossier archivé.");
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Archivage impossible.");
    }
  }

  async function handleRunDueAlerts() {
    try {
      const result = await apiFetch<{ due_soon: number; overdue: number }>("/notifications/due-alerts/run", {
        method: "POST",
      });
      setActiveFeature("notifications");
      setAppMessage(`${result.due_soon} échéance(s) proche(s), ${result.overdue} retard(s) notifiés.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Analyse des échéances impossible.");
    }
  }

  async function handleMarkNotificationRead(notificationId: string) {
    try {
      await apiFetch<NotificationItem>(`/notifications/${notificationId}/read`, {
        method: "PATCH",
      });
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Mise à jour notification impossible.");
    }
  }

  async function handleMarkAllNotificationsRead() {
    try {
      const result = await apiFetch<{ updated: number }>("/notifications/read-all", {
        method: "PATCH",
      });
      setAppMessage(`${result.updated} notification(s) marquée(s) comme lue(s).`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Mise à jour notifications impossible.");
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

  async function handleDownloadAttachment(caseId: string, attachment: Attachment) {
    try {
      const response = await fetch(`${apiUrl}/cases/${caseId}/attachments/${attachment.id}/download`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? `Erreur API ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = attachment.file_name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setAppMessage(`Téléchargement sécurisé: ${attachment.file_name}`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Téléchargement impossible.");
    }
  }

  async function handleAuditExport(format: "csv" | "pdf", action: string) {
    const params = new URLSearchParams({ format });
    if (action !== "ALL") params.set("action", action);
    const path = `/audit-logs/export?${params.toString()}`;
    try {
      const performRequest = (token: string) => fetch(`${apiUrl}${path}`, { headers: { Authorization: `Bearer ${token}` } });
      let response = await performRequest(accessToken);
      if (response.status === 401) response = await performRequest(await refreshAccessToken());
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? `Erreur API ${response.status}`);
      }
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] ?? `infobridge-audit.${format}`;
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setAppMessage(`Journal d’audit exporté en ${format.toUpperCase()}.`);
      await loadWorkspaceData();
    } catch (error) {
      setAppMessage(error instanceof Error ? error.message : "Export du journal impossible.");
    }
  }

  function handleMissingAttachment(reference: string) {
    setActiveFeature("upload-document");
    setAppMessage(`Aucune pièce jointe pour ${reference}. Ajoutez d'abord un document au dossier.`);
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
    const section = getFeatureSection(feature, userRole === "admin" || userRole === "auditor");
    setActiveSection(section);
    setActiveFeature(feature);
    setWorkflowDraft(null);
    if (feature === "retention") {
      setCaseStatusFilter("ALL");
    }

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

  function clearLocalSession() {
    sessionStorage.removeItem("infobridge_session");
    sessionStorage.removeItem("infobridge_token");
    sessionStorage.removeItem("infobridge_refresh_token");
    sessionStorage.removeItem("infobridge_role");
    sessionStorage.removeItem("infobridge_user");
    setIsAuthenticated(false);
    setAccessToken("");
    setCurrentUser(null);
    setUserRole("user");
    setActiveSection("documents");
  }

  async function handleLogout() {
    try {
      await fetch(`${apiUrl}/auth/logout`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        method: "POST",
      });
    } finally {
      clearLocalSession();
    }
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
                  setActiveFeature(userRole === "auditor" && item.id === "admin" ? "audit" : null);
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
              <input
                aria-label="Rechercher"
                onChange={(event) => {
                  setCaseSearch(event.target.value);
                  setActiveSection("documents");
                  setActiveFeature("search");
                }}
                placeholder="Rechercher un dossier, une institution..."
                type="search"
                value={caseSearch}
              />
            </label>
            <button
              aria-label="Notifications"
              className="icon-button notification-trigger"
              onClick={() => {
                setActiveFeature("notifications");
                setActiveSection("documents");
              }}
              type="button"
            >
              <Bell size={18} />
              {unreadNotificationCount ? <span>{unreadNotificationCount}</span> : null}
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

        {activeSection === "overview" ? <Overview auditLogs={auditLogs} metrics={metrics} securityEvents={securityEvents} /> : null}
        {appMessage ? <p className="app-message">{appMessage}</p> : null}
        {loadError ? <p className="app-message" role="alert">{loadError} <button className="ghost-button" onClick={() => void loadWorkspaceData()} type="button">Réessayer</button></p> : null}
        {activeSection === "admin" ? (
          <AdminWorkspace
            apiClientCredential={apiClientCredential}
            apiClients={apiClients}
            apiScopes={apiScopes}
            auditLogs={auditLogs}
            adminDraft={adminDraft}
            canEditPlatformSettings={currentUser?.role === "SYSTEM_ADMIN"}
            currentUser={currentUser}
            institutions={institutions}
            onCancelAdminDraft={() => setAdminDraft(null)}
            onCreateInstitution={handleCreateInstitution}
            onCreateUser={handleCreateUser}
            onExportAudit={handleAuditExport}
            onApiClientCredentialClose={() => setApiClientCredential(null)}
            onApiClientStatus={handleApiClientStatus}
            onCreateApiClient={handleCreateApiClient}
            onInstitutionStatus={handleInstitutionStatus}
            onUpdateInstitution={handleUpdateInstitution}
            onUpdateApiClient={handleUpdateApiClient}
            onUpdatePlatformSetting={handleUpdatePlatformSetting}
            onUpdateReferenceItem={handleUpdateReferenceItem}
            onRotateApiClientSecret={handleRotateApiClientSecret}
            onRevokeUserSessions={handleRevokeUserSessions}
            onUpdateUser={handleUpdateUser}
            onUserStatus={handleUserStatus}
            activeFeature={activeFeature}
            onOpenAdminDraft={setAdminDraft}
            platformSettings={platformSettings}
            referenceItems={referenceItems}
            securityEvents={securityEvents}
            users={users}
          />
        ) : null}
        {activeSection === "documents" ? (
          <DocumentsWorkspace
            attachmentsByCase={attachmentsByCase}
            activeFeature={activeFeature}
            currentUser={currentUser}
            caseClassificationFilter={caseClassificationFilter}
            casePriorityFilter={casePriorityFilter}
            caseSearch={caseSearch}
            caseStatusFilter={caseStatusFilter}
            exchangeCases={exchangeCases}
            institutions={institutions}
            lifecycleStatus={lifecycleStatus}
            onAssignCase={handleAssignCase}
            onArchiveCase={handleArchiveCase}
            onCreateCase={handleCreateCase}
            notificationLevel={notificationLevel}
            notifications={notifications}
            onMarkAllNotificationsRead={handleMarkAllNotificationsRead}
            onMarkNotificationRead={handleMarkNotificationRead}
            onRunDueAlerts={handleRunDueAlerts}
            onReceipt={handleReceipt}
            onSetNotificationLevel={setNotificationLevel}
            onSetCaseClassificationFilter={setCaseClassificationFilter}
            onSetCasePriorityFilter={setCasePriorityFilter}
            onSetCaseSearch={setCaseSearch}
            onSetCaseStatusFilter={setCaseStatusFilter}
            onDraftResponse={openDraftResponse}
            onDownloadAttachment={handleDownloadAttachment}
            onMissingAttachment={handleMissingAttachment}
            onUploadAttachment={handleUploadAttachment}
            onValidateResponse={openValidation}
            onWorkflowAction={handleWorkflowAction}
            receiptsByCase={receiptsByCase}
            referenceItems={referenceItems}
            onWorkflowDraftCancel={() => setWorkflowDraft(null)}
            onWorkflowDraftSubmit={handleWorkflowDraftSubmit}
            users={assignees}
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
        {
          description: "Libellés, ordre et valeurs disponibles",
          feature: "admin-references",
          icon: SlidersHorizontal,
          label: "Référentiels",
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

function getFeatureSection(feature: FeatureKey, canSupervise: boolean): AppSection {
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
      "admin-references",
      "integrations",
      "backup",
      "audit",
    ].includes(feature) &&
    canSupervise
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
    "admin-references": "Référentiels configurables",
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
    retention: "Consultez les dossiers clôturés à archiver et les dossiers archivés avec leur échéance de conservation.",
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

function CapabilityPanel({ feature, onRunDueAlerts }: { feature: FeatureKey; onRunDueAlerts?: () => void }) {
  return (
    <section className="capability-panel">
      <div className="panel-toolbar">
        <div>
          <h2>{getFeatureTitle(feature)}</h2>
          <p>Module prévu dans la trajectoire fonctionnelle InfoBridge.</p>
        </div>
        {feature === "notifications" && onRunDueAlerts ? (
          <button className="ghost-button" onClick={onRunDueAlerts} type="button">
            <Bell size={17} />
            Scanner échéances
          </button>
        ) : null}
      </div>
      <div className="capability-body">
        <StatusPill label={feature === "notifications" ? "Branché" : "À brancher"} />
        <p>
          {feature === "notifications"
            ? "Les alertes d'échéance proche et de retard peuvent être générées à partir des dossiers ouverts."
            : "L'accès rapide est déjà présent pour structurer l'interface. La prochaine étape consiste à relier ce module à ses écrans et endpoints dédiés."}
        </p>
      </div>
    </section>
  );
}

function NotificationsPanel({
  canRunDueAlerts,
  lifecycleStatus,
  notificationLevel,
  notifications,
  onMarkAllRead,
  onMarkRead,
  onRunDueAlerts,
  onSetLevel,
}: {
  canRunDueAlerts: boolean;
  lifecycleStatus: LifecycleStatus | null;
  notificationLevel: string;
  notifications: NotificationItem[];
  onMarkAllRead: () => void;
  onMarkRead: (notificationId: string) => void;
  onRunDueAlerts: () => void;
  onSetLevel: (level: string) => void;
}) {
  const unreadCount = notifications.filter((notification) => !notification.read).length;

  return (
    <section className="notifications-panel" id="notifications-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Notifications et alertes</h2>
          <p>{unreadCount} notification(s) non lue(s) dans le filtre courant</p>
          <small className="scheduler-status">
            {lifecycleStatus?.enabled && lifecycleStatus.due_alerts_enabled
              ? `Relances automatiques toutes les ${formatInterval(lifecycleStatus.interval_seconds)} · seuil ${lifecycleStatus.due_soon_hours} h${lifecycleStatus.last_completed_at ? ` · dernier passage ${formatDate(lifecycleStatus.last_completed_at)}` : ""}`
              : "Relances automatiques désactivées"}
          </small>
        </div>
        <div className="toolbar-actions">
          <select value={notificationLevel} onChange={(event) => onSetLevel(event.target.value)}>
            <option value="ALL">Tous niveaux</option>
            <option value="INFO">Information</option>
            <option value="WARNING">Avertissement</option>
            <option value="ERROR">Erreur</option>
          </select>
          {canRunDueAlerts ? (
            <button className="ghost-button" onClick={onRunDueAlerts} type="button">
              <Bell size={17} />
              Exécuter maintenant
            </button>
          ) : null}
          <button className="ghost-button" onClick={onMarkAllRead} type="button">
            <CheckCircle2 size={17} />
            Tout lu
          </button>
        </div>
      </div>

      <div className="notification-list">
        {notifications.length ? (
          notifications.map((notification) => (
            <article className={notification.read ? "notification-row read" : "notification-row"} key={notification.id}>
              <span className={`notification-level ${notification.level.toLowerCase()}`}>
                {notification.level === "ERROR" ? <AlertTriangle size={17} /> : <Bell size={17} />}
              </span>
              <div>
                <strong>{notification.title}</strong>
                <p>{notification.body}</p>
                <small>{formatDate(notification.created_at)}</small>
              </div>
              <StatusPill label={notification.read ? "Lue" : "Non lue"} />
              {!notification.read ? (
                <button className="ghost-button" onClick={() => onMarkRead(notification.id)} type="button">
                  Marquer lu
                </button>
              ) : null}
            </article>
          ))
        ) : (
          <p className="empty-state">Aucune notification dans ce filtre.</p>
        )}
      </div>
    </section>
  );
}

function Overview({
  auditLogs,
  metrics,
  securityEvents,
}: {
  auditLogs: AuditLogItem[];
  metrics: Array<{ icon: typeof Building2; label: string; value: number; delta: string }>;
  securityEvents: SecurityEventItem[];
}) {
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
        <InsightRail auditLogs={auditLogs} securityEvents={securityEvents} />
      </section>
    </>
  );
}

function AdminWorkspace({
  activeFeature,
  adminDraft,
  apiClientCredential,
  apiClients,
  apiScopes,
  auditLogs,
  canEditPlatformSettings,
  currentUser,
  institutions,
  onApiClientCredentialClose,
  onApiClientStatus,
  onCancelAdminDraft,
  onCreateApiClient,
  onCreateInstitution,
  onCreateUser,
  onExportAudit,
  onInstitutionStatus,
  onUpdateInstitution,
  onUpdateApiClient,
  onUpdatePlatformSetting,
  onUpdateReferenceItem,
  onRotateApiClientSecret,
  onRevokeUserSessions,
  onUpdateUser,
  onUserStatus,
  onOpenAdminDraft,
  platformSettings,
  referenceItems,
  securityEvents,
  users,
}: {
  activeFeature: FeatureKey | null;
  adminDraft: AdminDraft;
  apiClientCredential: ApiClientCredential | null;
  apiClients: ApiClientItem[];
  apiScopes: ApiScopeItem[];
  auditLogs: AuditLogItem[];
  canEditPlatformSettings: boolean;
  currentUser: AuthUser | null;
  institutions: Institution[];
  onApiClientCredentialClose: () => void;
  onApiClientStatus: (client: ApiClientItem) => void;
  onCancelAdminDraft: () => void;
  onCreateApiClient: (event: FormEvent<HTMLFormElement>) => void;
  onCreateInstitution: (event: FormEvent<HTMLFormElement>) => void;
  onCreateUser: (event: FormEvent<HTMLFormElement>) => void;
  onExportAudit: (format: "csv" | "pdf", action: string) => void;
  onInstitutionStatus: (institutionId: string, status: string) => void;
  onUpdateInstitution: (institutionId: string, event: FormEvent<HTMLFormElement>) => void;
  onUpdateApiClient: (client: ApiClientItem, event: FormEvent<HTMLFormElement>) => void;
  onUpdatePlatformSetting: (key: string, value: boolean | number) => void;
  onUpdateReferenceItem: (item: ReferenceItem, event: FormEvent<HTMLFormElement>) => void;
  onRotateApiClientSecret: (client: ApiClientItem) => void;
  onRevokeUserSessions: (userId: string) => void;
  onUpdateUser: (userId: string, event: FormEvent<HTMLFormElement>) => void;
  onUserStatus: (userId: string, status: string) => void;
  onOpenAdminDraft: (draft: AdminDraft) => void;
  platformSettings: PlatformSetting[];
  referenceItems: ReferenceItem[];
  securityEvents: SecurityEventItem[];
  users: PlatformUser[];
}) {
  const editedUser = adminDraft && typeof adminDraft === "object" && "user" in adminDraft ? adminDraft.user : null;
  const editedInstitution = adminDraft && typeof adminDraft === "object" && "institution" in adminDraft ? adminDraft.institution : null;
  const adminFormPanelRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!adminDraft) return;
    const panel = adminFormPanelRef.current;
    panel?.scrollIntoView({ block: "start", behavior: "instant" });
    panel?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
  }, [adminDraft]);
  const institutionTypeOptions = getReferenceOptions(referenceItems, "institution_type", true);
  return (
    <section className="admin-layout">
      {adminDraft ? (
        <section className="settings-panel admin-editor" ref={adminFormPanelRef} aria-labelledby="admin-editor-title">
          <div className="panel-toolbar">
            <div>
              <h2 id="admin-editor-title">{adminDraft === "institution" ? "Nouvelle institution" : editedInstitution ? "Modifier l’institution" : editedUser ? "Modifier l’utilisateur" : "Nouvel utilisateur"}</h2>
              <p>
                {adminDraft === "institution" || editedInstitution
                  ? editedInstitution ? "Mettre à jour l’identité de l’institution." : "Enregistrer une institution participante."
                  : editedUser ? "Mettre à jour son identité, son institution et son rôle." : "Créer un compte et lui attribuer un rôle."}
              </p>
            </div>
            <button className="ghost-button" onClick={onCancelAdminDraft} type="button">
              Annuler
            </button>
          </div>

          {adminDraft === "institution" || editedInstitution ? (
            <form key={editedInstitution?.id ?? "new-institution"} className="request-form admin-form" onSubmit={editedInstitution ? (event) => onUpdateInstitution(editedInstitution.id, event) : onCreateInstitution}>
              <label>
                <span>Nom</span>
                <input defaultValue={editedInstitution?.name} name="name" placeholder="Ministère, agence, banque..." required />
              </label>
              <label>
                <span>Code</span>
                <input defaultValue={editedInstitution?.code} name="code" placeholder="MINFIN" required />
              </label>
              <label>
                <span>Type</span>
                <select defaultValue={editedInstitution?.type ?? "AGENCY"} name="type">
                  {institutionTypeOptions.map((item) => (
                    <option disabled={!item.active && item.code !== editedInstitution?.type} key={item.code} value={item.code}>
                      {item.label}{item.active ? "" : " (désactivé)"}
                    </option>
                  ))}
                </select>
              </label>
              <button className="primary-button" type="submit">
                <Building2 size={18} />
                {editedInstitution ? "Enregistrer" : "Créer institution"}
              </button>
            </form>
          ) : (
            <form key={editedUser?.id ?? "new-user"} className="request-form admin-form" onSubmit={editedUser ? (event) => onUpdateUser(editedUser.id, event) : onCreateUser}>
              <label>
                <span>Nom complet</span>
                <input defaultValue={editedUser?.full_name} name="full_name" placeholder="Nom de l'utilisateur" required />
              </label>
              <label>
                <span>E-mail</span>
                <input defaultValue={editedUser?.email} name="email" placeholder="user@institution.bi" required type="email" />
              </label>
              {!editedUser ? (
                <label>
                  <span>Mot de passe initial</span>
                  <input name="password" minLength={12} placeholder="Mot de passe temporaire" required type="password" />
                </label>
              ) : null}
              <label>
                <span>Institution</span>
                <select defaultValue={editedUser?.institution_id ?? ""} name="institution_id" required>
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
                <select defaultValue={editedUser?.role ?? "AGENT"} name="role">
                  <option value="SYSTEM_ADMIN">Administrateur système</option>
                  <option value="AGENT">Agent</option>
                  <option value="VALIDATOR">Validateur</option>
                  <option value="CONSULTANT">Consultant</option>
                  <option value="OBSERVER">Observateur</option>
                  <option value="AUDITOR">Auditeur</option>
                  <option value="INSTITUTION_ADMIN">Admin institution</option>
                </select>
              </label>
              <button className="primary-button" type="submit">
                <Users size={18} />
                {editedUser ? "Enregistrer" : "Créer utilisateur"}
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
                    {institution.code} · {referenceLabel(referenceItems, "institution_type", institution.type)}
                  </p>
                </div>
                <StatusPill label={institution.status === "ACTIVE" ? "Active" : institution.status} />
                <small>{institution.type}</small>
                <div className="row-actions">
                  <button className="secondary-button" aria-label={`Modifier ${institution.name}`} onClick={() => onOpenAdminDraft({ institution })} type="button">
                    <Pencil size={16} aria-hidden="true" />
                    Modifier
                  </button>
                  <button className={institution.status === "ACTIVE" ? "ghost-button danger-button" : "ghost-button"} onClick={() => onInstitutionStatus(institution.id, institution.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE")} type="button">
                    {institution.status === "ACTIVE" ? "Suspendre" : "Réactiver"}
                  </button>
                </div>
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
                <div className="row-actions">
                  <button className="secondary-button" aria-label={`Modifier ${user.full_name}`} onClick={() => onOpenAdminDraft({ user })} type="button">
                    <Pencil size={16} aria-hidden="true" />
                    Modifier
                  </button>
                  <button className="ghost-button danger-button" onClick={() => onRevokeUserSessions(user.id)} type="button">
                    Révoquer sessions
                  </button>
                  <button className={user.status === "ACTIVE" ? "ghost-button danger-button" : "ghost-button"} onClick={() => onUserStatus(user.id, user.status === "ACTIVE" ? "DISABLED" : "ACTIVE")} type="button">
                    {user.status === "ACTIVE" ? "Désactiver" : "Réactiver"}
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="empty-state">Aucun utilisateur chargé.</p>
          )}
        </div>
      </section>
      ) : null}

      {activeFeature === "admin-governance" || activeFeature === "access" ? (
        <PlatformSettingsPanel
          canEdit={canEditPlatformSettings}
          onUpdate={onUpdatePlatformSetting}
          settings={platformSettings}
        />
      ) : null}

      {activeFeature === "admin-references" ? (
        <ReferenceDataPanel
          canEdit={canEditPlatformSettings}
          items={referenceItems}
          onUpdate={onUpdateReferenceItem}
        />
      ) : null}

      {activeFeature === "audit" ? (
        <AuditSecurityPanel auditLogs={auditLogs} onExport={onExportAudit} securityEvents={securityEvents} />
      ) : null}

      {activeFeature === "integrations" ? (
        <ApiClientsPanel
          clients={apiClients}
          credential={apiClientCredential}
          currentUser={currentUser}
          institutions={institutions}
          onCredentialClose={onApiClientCredentialClose}
          onCreate={onCreateApiClient}
          onRotateSecret={onRotateApiClientSecret}
          onStatus={onApiClientStatus}
          onUpdate={onUpdateApiClient}
          scopes={apiScopes}
        />
      ) : null}

      {activeFeature === "backup" || activeFeature === "notifications" ? (
        <CapabilityPanel feature={activeFeature} />
      ) : null}
    </section>
  );
}

function PlatformSettingsPanel({
  canEdit,
  onUpdate,
  settings,
}: {
  canEdit: boolean;
  onUpdate: (key: string, value: boolean | number) => void;
  settings: PlatformSetting[];
}) {
  const categories: Array<{ key: PlatformSetting["category"]; title: string }> = [
    { key: "SECURITY", title: "Sécurité et sessions" },
    { key: "RETENTION", title: "Conservation documentaire" },
    { key: "AUTOMATION", title: "Automatisation" },
  ];
  return (
    <section className="settings-panel" id="admin-governance-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Paramètres de sécurité et de conservation</h2>
          <p>{canEdit ? "Les modifications prennent effet immédiatement." : "Consultation seule — modification réservée à l’administrateur système."}</p>
        </div>
        <StatusPill label={canEdit ? "Modifiable" : "Lecture seule"} />
      </div>
      <div className="platform-settings-groups">
        {categories.map((category) => (
          <section key={category.key}>
            <h3>{category.title}</h3>
            <div className="settings-list">
              {settings.filter((setting) => setting.category === category.key).map((setting) => (
                <form
                  className="platform-setting-row"
                  key={setting.key}
                  onSubmit={(event) => {
                    event.preventDefault();
                    const rawValue = String(new FormData(event.currentTarget).get("value") ?? "");
                    onUpdate(setting.key, setting.value_type === "boolean" ? rawValue === "true" : Number(rawValue));
                  }}
                >
                  <div>
                    <strong>{setting.label}</strong>
                    <p>{setting.description}</p>
                    <small>Source : {setting.source === "database" ? "base de données" : "environnement"}</small>
                  </div>
                  {setting.value_type === "boolean" ? (
                    <select defaultValue={String(setting.value)} disabled={!canEdit} name="value">
                      <option value="true">Activé</option>
                      <option value="false">Désactivé</option>
                    </select>
                  ) : (
                    <input
                      defaultValue={Number(setting.value)}
                      disabled={!canEdit}
                      max={setting.maximum ?? undefined}
                      min={setting.minimum ?? undefined}
                      name="value"
                      required
                      type="number"
                    />
                  )}
                  {canEdit ? <button className="ghost-button" type="submit">Enregistrer</button> : null}
                </form>
              ))}
            </div>
          </section>
        ))}
        <div className="setting-row">
          <span>MFA obligatoire</span>
          <strong className="warning">Non implémenté</strong>
        </div>
        {!settings.length ? <p className="empty-state">Aucun paramètre chargé. Appliquez la migration 0014.</p> : null}
      </div>
    </section>
  );
}

function ReferenceDataPanel({
  canEdit,
  items,
  onUpdate,
}: {
  canEdit: boolean;
  items: ReferenceItem[];
  onUpdate: (item: ReferenceItem, event: FormEvent<HTMLFormElement>) => void;
}) {
  const catalogs = [...new Map(items.map((item) => [item.catalog, item.catalog_label])).entries()];
  return (
    <section className="settings-panel" id="admin-reference-data-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Référentiels configurables</h2>
          <p>Personnalisez les libellés, descriptions, ordre d’affichage et valeurs proposées aux utilisateurs.</p>
        </div>
        <StatusPill label={canEdit ? "Modifiable" : "Lecture seule"} />
      </div>
      <div className="reference-catalogs">
        {catalogs.map(([catalog, catalogLabel]) => (
          <section className="reference-catalog" key={catalog}>
            <h3>{catalogLabel}</h3>
            <div className="reference-header" aria-hidden="true">
              <span>Code et libellé</span><span>Description</span><span>Ordre</span><span>État</span><span />
            </div>
            {getReferenceOptions(items, catalog, true).map((item) => (
              <form className="reference-row" key={item.code} onSubmit={(event) => onUpdate(item, event)}>
                <label>
                  <span>{item.code}</span>
                  <input defaultValue={item.label} disabled={!canEdit} name="label" required />
                </label>
                <input
                  aria-label={`Description de ${item.code}`}
                  defaultValue={item.description ?? ""}
                  disabled={!canEdit}
                  name="description"
                  placeholder="Description"
                />
                <input
                  aria-label={`Ordre de ${item.code}`}
                  defaultValue={item.sort_order}
                  disabled={!canEdit}
                  min="0"
                  name="sort_order"
                  required
                  type="number"
                />
                <select
                  aria-label={`État de ${item.code}`}
                  defaultValue={String(item.active)}
                  disabled={!canEdit || item.required_active}
                  name="active"
                >
                  <option value="true">Active</option>
                  <option value="false">Désactivée</option>
                </select>
                {item.required_active ? <input name="active" type="hidden" value="true" /> : null}
                {canEdit ? <button className="ghost-button" type="submit">Enregistrer</button> : null}
              </form>
            ))}
          </section>
        ))}
        {!items.length ? <p className="empty-state">Aucun référentiel chargé. Appliquez la migration 0015.</p> : null}
      </div>
    </section>
  );
}

function ApiClientsPanel({
  clients,
  credential,
  currentUser,
  institutions,
  onCreate,
  onCredentialClose,
  onRotateSecret,
  onStatus,
  onUpdate,
  scopes,
}: {
  clients: ApiClientItem[];
  credential: ApiClientCredential | null;
  currentUser: AuthUser | null;
  institutions: Institution[];
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onCredentialClose: () => void;
  onRotateSecret: (client: ApiClientItem) => void;
  onStatus: (client: ApiClientItem) => void;
  onUpdate: (client: ApiClientItem, event: FormEvent<HTMLFormElement>) => void;
  scopes: ApiScopeItem[];
}) {
  const isSystemAdmin = currentUser?.role === "SYSTEM_ADMIN";
  return (
    <section className="settings-panel" id="api-clients-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Authentification machine à machine</h2>
          <p>Clients techniques, secrets rotatifs et scopes limités au strict nécessaire.</p>
        </div>
        <StatusPill label={`${clients.filter((client) => client.active).length} actif(s)`} />
      </div>

      {credential ? (
        <div className="credential-panel" role="status">
          <div>
            <strong>Identifiants affichés une seule fois</strong>
            <p>Copiez le secret maintenant. Il ne pourra pas être récupéré ultérieurement.</p>
          </div>
          <dl>
            <div><dt>Client ID</dt><dd><code>{credential.client_key}</code></dd></div>
            <div><dt>Secret</dt><dd><code>{credential.client_secret}</code></dd></div>
          </dl>
          <button className="ghost-button" onClick={onCredentialClose} type="button">J’ai copié les identifiants</button>
        </div>
      ) : null}

      <form className="request-form api-client-create" onSubmit={onCreate}>
        <label>
          <span>Nom du client</span>
          <input name="name" placeholder="Connecteur GED" required />
        </label>
        <label>
          <span>Institution</span>
          {isSystemAdmin ? (
            <select defaultValue="" name="institution_id">
              <option value="">Toutes les institutions</option>
              {institutions.filter((institution) => institution.status === "ACTIVE").map((institution) => (
                <option key={institution.id} value={institution.id}>{institution.name}</option>
              ))}
            </select>
          ) : (
            <>
              <input name="institution_id" type="hidden" value={currentUser?.institution_id ?? ""} />
              <input disabled value={institutions.find((item) => item.id === currentUser?.institution_id)?.name ?? "Institution"} />
            </>
          )}
        </label>
        <fieldset className="scope-fieldset">
          <legend>Scopes accordés</legend>
          {scopes.map((scope) => (
            <label key={scope.code} title={scope.description}>
              <input name="scopes" type="checkbox" value={scope.code} />
              <span>{scope.label}</span>
              <small>{scope.code}</small>
            </label>
          ))}
        </fieldset>
        <button className="primary-button" type="submit"><KeyRound size={17} />Créer le client</button>
      </form>

      <div className="api-client-list">
        {clients.map((client) => {
          const institution = institutions.find((item) => item.id === client.institution_id);
          return (
            <form className="api-client-card" key={client.id} onSubmit={(event) => onUpdate(client, event)}>
              <div className="api-client-heading">
                <div>
                  <input defaultValue={client.name} disabled={!client.active} name="name" required />
                  <code>{client.client_key}</code>
                </div>
                <StatusPill label={client.active ? "Actif" : "Suspendu"} />
              </div>
              <p>{institution?.name ?? "Périmètre global"} · version de jeton {client.token_version}</p>
              <fieldset className="scope-fieldset compact" disabled={!client.active}>
                <legend>Scopes</legend>
                {scopes.map((scope) => (
                  <label key={scope.code} title={scope.description}>
                    <input defaultChecked={client.scopes.includes(scope.code)} name="scopes" type="checkbox" value={scope.code} />
                    <span>{scope.label}</span>
                    <small>{scope.code}</small>
                  </label>
                ))}
              </fieldset>
              <small>Dernière utilisation : {client.last_used_at ? formatDateTime(client.last_used_at) : "jamais"}</small>
              <div className="row-actions">
                {client.active ? <button className="ghost-button" type="submit">Enregistrer les scopes</button> : null}
                <button className="ghost-button" disabled={!client.active} onClick={() => onRotateSecret(client)} type="button">Tourner le secret</button>
                <button className="ghost-button" onClick={() => onStatus(client)} type="button">{client.active ? "Suspendre" : "Réactiver"}</button>
              </div>
            </form>
          );
        })}
        {!clients.length ? <p className="empty-state">Aucun client M2M enregistré.</p> : null}
      </div>
    </section>
  );
}

function DocumentsWorkspace({
  activeFeature,
  attachmentsByCase,
  caseClassificationFilter,
  casePriorityFilter,
  caseSearch,
  caseStatusFilter,
  currentUser,
  exchangeCases,
  institutions,
  lifecycleStatus,
  notificationLevel,
  notifications,
  onAssignCase,
  onArchiveCase,
  onCreateCase,
  onDraftResponse,
  onDownloadAttachment,
  onMarkAllNotificationsRead,
  onMarkNotificationRead,
  onMissingAttachment,
  onRunDueAlerts,
  onReceipt,
  onSetCaseClassificationFilter,
  onSetCasePriorityFilter,
  onSetCaseSearch,
  onSetCaseStatusFilter,
  onSetNotificationLevel,
  onUploadAttachment,
  onValidateResponse,
  onWorkflowAction,
  receiptsByCase,
  onWorkflowDraftCancel,
  onWorkflowDraftSubmit,
  referenceItems,
  users,
  workflowDraft,
}: {
  activeFeature: FeatureKey | null;
  attachmentsByCase: Record<string, Attachment[]>;
  caseClassificationFilter: string;
  casePriorityFilter: string;
  caseSearch: string;
  caseStatusFilter: string;
  currentUser: AuthUser | null;
  exchangeCases: ExchangeCase[];
  institutions: Institution[];
  lifecycleStatus: LifecycleStatus | null;
  notificationLevel: string;
  notifications: NotificationItem[];
  onAssignCase: (caseId: string, assignedTo: string) => void;
  onArchiveCase: (caseId: string) => void;
  onCreateCase: (event: FormEvent<HTMLFormElement>) => void;
  onDraftResponse: (caseId: string) => void;
  onDownloadAttachment: (caseId: string, attachment: Attachment) => void;
  onMarkAllNotificationsRead: () => void;
  onMarkNotificationRead: (notificationId: string) => void;
  onMissingAttachment: (reference: string) => void;
  onRunDueAlerts: () => void;
  onReceipt: (caseId: string, markRead: boolean) => void;
  onSetCaseClassificationFilter: (value: string) => void;
  onSetCasePriorityFilter: (value: string) => void;
  onSetCaseSearch: (value: string) => void;
  onSetCaseStatusFilter: (value: string) => void;
  onSetNotificationLevel: (level: string) => void;
  onUploadAttachment: (event: FormEvent<HTMLFormElement>) => void;
  onValidateResponse: (caseId: string, approved: boolean) => void;
  onWorkflowAction: (caseId: string, action: "send" | "receive" | "start" | "send-response" | "close") => void;
  receiptsByCase: Record<string, Receipt[]>;
  onWorkflowDraftCancel: () => void;
  onWorkflowDraftSubmit: (event: FormEvent<HTMLFormElement>) => void;
  referenceItems: ReferenceItem[];
  users: PlatformUser[];
  workflowDraft: WorkflowDraft;
}) {
  const currentInstitution = institutions.find((institution) => institution.id === currentUser?.institution_id);
  const receivers = institutions.filter((institution) => institution.id !== currentUser?.institution_id);
  const availableReceivers = receivers.length ? receivers : institutions;
  const classificationOptions = getReferenceOptions(referenceItems, "classification");
  const priorityOptions = getReferenceOptions(referenceItems, "case_priority");
  const attachmentPurposeOptions = getReferenceOptions(referenceItems, "attachment_purpose");
  const listFeatures: Array<FeatureKey | null> = [
    "cases",
    "secure-transmission",
    "receive-assign",
    "processing",
    "validation",
    "secure-response",
    "lifecycle",
    "retention",
    "classification",
    "search",
  ];
  const shouldShowCases = listFeatures.includes(activeFeature);
  const normalizedSearch = caseSearch.trim().toLocaleLowerCase("fr");
  const filteredCases = getCasesForFeature(exchangeCases, activeFeature, currentUser?.id ?? null).filter((item) => {
    const sender = institutions.find((institution) => institution.id === item.sender_institution_id);
    const receiver = institutions.find((institution) => institution.id === item.receiver_institution_id);
    const searchableText = [item.reference, item.subject, item.description, item.response_body, sender?.name, receiver?.name]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase("fr");
    return (
      (!normalizedSearch || searchableText.includes(normalizedSearch)) &&
      (caseStatusFilter === "ALL" || item.status === caseStatusFilter) &&
      (casePriorityFilter === "ALL" || item.priority === casePriorityFilter) &&
      (caseClassificationFilter === "ALL" || item.classification === caseClassificationFilter)
    );
  });
  const classificationStats = getClassificationStats(exchangeCases, referenceItems);
  const visibleNotifications =
    notificationLevel === "ALL"
      ? notifications
      : notifications.filter((notification) => notification.level === notificationLevel);
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
            <select defaultValue="INTERNE" name="classification">
              {classificationOptions.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
            </select>
          </label>
          <label>
            <span>Priorité</span>
            <select defaultValue="NORMAL" name="priority">
              {priorityOptions.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
            </select>
          </label>
          <label>
            <span>Échéance</span>
            <input name="due_at" type="datetime-local" />
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
            <span>Usage</span>
            <select defaultValue="REQUEST" name="purpose">
              {attachmentPurposeOptions.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
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
              <StatusPill label={item.label} />
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

        <div className="case-filters" aria-label="Filtres des demandes">
          <label className="document-search">
            <Search size={17} />
            <input onChange={(event) => onSetCaseSearch(event.target.value)} placeholder="Référence, objet ou institution" type="search" value={caseSearch} />
          </label>
          <select aria-label="Filtrer par statut" onChange={(event) => onSetCaseStatusFilter(event.target.value)} value={caseStatusFilter}>
            <option value="ALL">Tous les statuts</option>
            {(activeFeature === "retention" ? ["CLOSED", "ARCHIVED"] : ["DRAFT", "SENT", "RECEIVED", "ASSIGNED", "IN_PROGRESS", "PENDING_VALIDATION", "APPROVED", "REJECTED", "RESPONSE_SENT", "CLOSED", "ARCHIVED"]).map((caseStatus) => (
              <option key={caseStatus} value={caseStatus}>{formatStatus(caseStatus)}</option>
            ))}
          </select>
          <select aria-label="Filtrer par priorité" onChange={(event) => onSetCasePriorityFilter(event.target.value)} value={casePriorityFilter}>
            <option value="ALL">Toutes les priorités</option>
            {getReferenceOptions(referenceItems, "case_priority", true).map((item) => (
              <option key={item.code} value={item.code}>{item.label}</option>
            ))}
          </select>
          <select aria-label="Filtrer par classification" onChange={(event) => onSetCaseClassificationFilter(event.target.value)} value={caseClassificationFilter}>
            <option value="ALL">Toutes classifications</option>
            {getReferenceOptions(referenceItems, "classification", true).map((item) => (
              <option key={item.code} value={item.code}>{item.label}</option>
            ))}
          </select>
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
              const caseReceipts = receiptsByCase[item.id] ?? [];
              const sender = institutions.find((institution) => institution.id === item.sender_institution_id);
              const receiver = institutions.find((institution) => institution.id === item.receiver_institution_id);
              const canAssign = users.length > 0 && ["RECEIVED", "IN_REVIEW"].includes(item.status);
              const primaryAttachment = caseAttachments[0];
              const currentReceipt = caseReceipts.find((receipt) => receipt.receiver_user_id === currentUser?.id);
              const canAcknowledge = item.status !== "DRAFT" && item.receiver_institution_id === currentUser?.institution_id;

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
                      <small>{caseAttachments.map((attachment) => `${attachment.file_name} (v${attachment.version})`).join(", ")}</small>
                    ) : null}
                    {activeFeature === "retention" ? (
                      <small>
                        {item.closed_at ? `Clôturé le ${formatDate(item.closed_at)} · ` : ""}
                        {item.status === "CLOSED"
                          ? "En attente d’archivage"
                          : item.retention_until
                            ? `Conservation jusqu’au ${formatDate(item.retention_until)}`
                            : "Échéance de conservation non définie"}
                      </small>
                    ) : null}
                    {caseReceipts.length ? (
                      <small className="receipt-summary">
                        {caseReceipts.map((receipt) => `${receipt.receiver_name} : ${receipt.read_at ? `lu le ${formatDate(receipt.read_at)}` : `reçu le ${formatDate(receipt.received_at)}`}`).join(" · ")}
                      </small>
                    ) : null}
                  </div>
                  <span className="document-type">{formatStatus(item.status)}</span>
                  <span className="document-date">{formatDate(item.created_at)}</span>
                  <span className="document-size">{caseAttachments.length} pièce(s)</span>
                  <StatusPill label={referenceLabel(referenceItems, "classification", item.classification)} />
                  <button
                    aria-label={
                      primaryAttachment
                        ? `Télécharger une pièce de ${item.reference}`
                        : `Ajouter une pièce à ${item.reference}`
                    }
                    className="icon-button"
                    onClick={() => {
                      if (primaryAttachment) {
                        onDownloadAttachment(item.id, primaryAttachment);
                        return;
                      }
                      onMissingAttachment(item.reference);
                    }}
                    type="button"
                    title={primaryAttachment ? "Télécharger la première pièce" : "Ajouter une pièce au dossier"}
                  >
                    {primaryAttachment ? <Download size={18} /> : <UploadCloud size={18} />}
                  </button>
                  <div className="workflow-actions">
                    {canAcknowledge && !currentReceipt ? (
                      <button className="ghost-button" onClick={() => onReceipt(item.id, false)} type="button">
                        Accuser réception
                      </button>
                    ) : null}
                    {canAcknowledge && currentReceipt && !currentReceipt.read_at ? (
                      <button className="ghost-button" onClick={() => onReceipt(item.id, true)} type="button">
                        Marquer lu
                      </button>
                    ) : null}
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
                    {item.status === "ASSIGNED" ? (
                      <button className="ghost-button" onClick={() => onWorkflowAction(item.id, "start")} type="button">
                        Démarrer
                      </button>
                    ) : null}
                    {["IN_PROGRESS", "REJECTED"].includes(item.status) ? (
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
                    {item.status === "CLOSED" && currentUser && (
                      currentUser.role === "SYSTEM_ADMIN" ||
                      (currentUser.role === "INSTITUTION_ADMIN" && item.sender_institution_id === currentUser.institution_id)
                    ) ? (
                      <button className="ghost-button" onClick={() => onArchiveCase(item.id)} type="button">
                        Archiver
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })
          ) : (
            <p className="empty-state">{activeFeature === "retention" ? "Aucun dossier clôturé ou archivé ne correspond aux filtres sélectionnés." : "Aucune demande ne correspond à cette vue."}</p>
          )}
        </div>
      </section>
      ) : null}

      {activeFeature === "notifications" ? (
        <NotificationsPanel
          canRunDueAlerts={Boolean(currentUser && ["SYSTEM_ADMIN", "INSTITUTION_ADMIN", "VALIDATOR"].includes(currentUser.role))}
          lifecycleStatus={lifecycleStatus}
          notificationLevel={notificationLevel}
          notifications={visibleNotifications}
          onMarkAllRead={onMarkAllNotificationsRead}
          onMarkRead={onMarkNotificationRead}
          onRunDueAlerts={onRunDueAlerts}
          onSetLevel={onSetNotificationLevel}
        />
      ) : null}

      {activeFeature &&
      !shouldShowCases &&
      activeFeature !== "access" &&
      activeFeature !== "new-case" &&
      activeFeature !== "upload-document" &&
      activeFeature !== "notifications" ? (
        <CapabilityPanel feature={activeFeature} onRunDueAlerts={onRunDueAlerts} />
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

function AuditSecurityPanel({
  auditLogs,
  onExport,
  securityEvents,
}: {
  auditLogs: AuditLogItem[];
  onExport: (format: "csv" | "pdf", action: string) => void;
  securityEvents: SecurityEventItem[];
}) {
  const [auditAction, setAuditAction] = useState("ALL");
  const [securitySeverity, setSecuritySeverity] = useState("ALL");
  const auditActions = [...new Set(auditLogs.map((log) => log.action))].sort();
  const visibleAuditLogs = auditAction === "ALL" ? auditLogs : auditLogs.filter((log) => log.action === auditAction);
  const visibleSecurityEvents = securitySeverity === "ALL"
    ? securityEvents
    : securityEvents.filter((event) => event.severity === securitySeverity);

  return (
    <div className="supervision-grid">
      <section className="settings-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Journal d’audit</h2>
            <p>{visibleAuditLogs.length} action(s) affichée(s)</p>
          </div>
          <div className="toolbar-actions">
            <select aria-label="Filtrer les actions d’audit" onChange={(event) => setAuditAction(event.target.value)} value={auditAction}>
              <option value="ALL">Toutes les actions</option>
              {auditActions.map((action) => <option key={action} value={action}>{formatAuditAction(action)}</option>)}
            </select>
            <button className="ghost-button" onClick={() => onExport("csv", auditAction)} type="button"><Download size={16} />CSV</button>
            <button className="ghost-button" onClick={() => onExport("pdf", auditAction)} type="button"><Download size={16} />PDF</button>
          </div>
        </div>
        <div className="audit-list detailed-event-list">
          {visibleAuditLogs.map((log) => (
            <article className="audit-item" key={log.id}>
              <span className="audit-icon neutral"><History size={16} /></span>
              <div>
                <strong>{formatAuditAction(log.action)}</strong>
                <p>{log.entity_type}{log.entity_id ? ` · ${log.entity_id}` : ""} · {formatDate(log.created_at)}</p>
                <small>{formatEventContext(log.ip_address, log.extra)}</small>
              </div>
            </article>
          ))}
          {!visibleAuditLogs.length ? <p className="empty-state">Aucun événement d’audit dans ce filtre.</p> : null}
        </div>
      </section>

      <section className="settings-panel">
        <div className="panel-toolbar">
          <div>
            <h2>Événements de sécurité</h2>
            <p>{visibleSecurityEvents.length} événement(s) affiché(s)</p>
          </div>
          <select aria-label="Filtrer la sévérité" onChange={(event) => setSecuritySeverity(event.target.value)} value={securitySeverity}>
            <option value="ALL">Toutes les sévérités</option>
            <option value="CRITICAL">Critique</option>
            <option value="HIGH">Élevée</option>
            <option value="MEDIUM">Moyenne</option>
            <option value="LOW">Faible</option>
          </select>
        </div>
        <div className="audit-list detailed-event-list">
          {visibleSecurityEvents.map((event) => (
            <article className="audit-item" key={event.id}>
              <span className={`audit-icon ${securityTone(event.severity)}`}><AlertTriangle size={16} /></span>
              <div>
                <strong>{formatAuditAction(event.event_type)}</strong>
                <p><StatusPill label={formatSeverity(event.severity)} /> · {formatDate(event.created_at)}</p>
                <small>{formatEventContext(event.ip_address, event.details)}{event.user_agent ? ` · ${event.user_agent}` : ""}</small>
              </div>
            </article>
          ))}
          {!visibleSecurityEvents.length ? <p className="empty-state">Aucun événement de sécurité dans ce filtre.</p> : null}
        </div>
      </section>
    </div>
  );
}

function InsightRail({ auditLogs, securityEvents }: { auditLogs: AuditLogItem[]; securityEvents: SecurityEventItem[] }) {
  const criticalCount = securityEvents.filter((event) => event.severity === "CRITICAL").length;
  const highCount = securityEvents.filter((event) => event.severity === "HIGH").length;
  return (
    <aside className="insight-rail" aria-label="Contrôle sécurité">
      <section className="security-card">
        <div className="security-score">
          <Fingerprint size={24} />
          <strong>{criticalCount + highCount}</strong>
        </div>
        <h2>Alertes prioritaires</h2>
        <p>{criticalCount} critique(s) et {highCount} élevée(s) dans les événements chargés.</p>
      </section>

      <section className="rail-section">
        <div className="rail-heading">
          <h2>Journal récent</h2>
          <span>Dernier chargement</span>
        </div>
        <div className="audit-list">
          {auditLogs.slice(0, 5).map((item) => (
            <div className="audit-item" key={item.id}>
              <span className="audit-icon neutral">
                <History size={16} />
              </span>
              <div>
                <strong>{formatAuditAction(item.action)}</strong>
                <p>{item.entity_type} · {formatDate(item.created_at)}</p>
              </div>
            </div>
          ))}
          {!auditLogs.length ? <p className="empty-state">Aucune activité récente.</p> : null}
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
    Lue: "received",
    "Non lue": "urgent",
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

  if (role === "auditor") {
    return navItems.filter((item) => item.id === "admin" || item.id === "documents");
  }

  return navItems.filter((item) => item.id === "documents");
}

function isAdminRole(role: AuthUser["role"]) {
  return role === "SYSTEM_ADMIN" || role === "INSTITUTION_ADMIN";
}

function formatRole(role: AuthUser["role"]) {
  const labels: Record<AuthUser["role"], string> = {
    AGENT: "Agent",
    AUDITOR: "Auditeur",
    INSTITUTION_ADMIN: "Admin institution",
    OBSERVER: "Observateur",
    CONSULTANT: "Consultant",
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

function formatAuditAction(action: string) {
  return action.toLocaleLowerCase("fr").replace(/_/g, " ").replace(/^./, (letter: string) => letter.toLocaleUpperCase("fr"));
}

function formatSeverity(severity: SecurityEventItem["severity"]) {
  return { CRITICAL: "Critique", HIGH: "Élevée", LOW: "Faible", MEDIUM: "Moyenne" }[severity];
}

function securityTone(severity: SecurityEventItem["severity"]) {
  if (severity === "CRITICAL" || severity === "HIGH") return "critical";
  if (severity === "MEDIUM") return "warning";
  return "success";
}

function formatEventContext(ipAddress: string | null, metadata: Record<string, unknown>) {
  const details = Object.entries(metadata)
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`);
  return [ipAddress ? `IP ${ipAddress}` : null, ...details].filter(Boolean).join(" · ") || "Aucun détail supplémentaire";
}

function formatInterval(seconds: number) {
  if (seconds % 3600 === 0) return `${seconds / 3600} h`;
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} s`;
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

  if (feature === "retention") {
    return items.filter((item) => ["CLOSED", "ARCHIVED"].includes(item.status));
  }

  if (feature === "classification") {
    return [...items].sort((first, second) => getClassificationRank(second.classification) - getClassificationRank(first.classification));
  }

  return items;
}

function getReferenceOptions(
  items: ReferenceItem[],
  catalog: ReferenceItem["catalog"],
  includeInactive = false,
) {
  return items
    .filter((item) => item.catalog === catalog && (includeInactive || item.active))
    .sort((first, second) => first.sort_order - second.sort_order || first.code.localeCompare(second.code));
}

function referenceLabel(items: ReferenceItem[], catalog: ReferenceItem["catalog"], code: string) {
  return items.find((item) => item.catalog === catalog && item.code === code)?.label ?? code;
}

function getClassificationStats(items: ExchangeCase[], referenceItems: ReferenceItem[]) {
  return getReferenceOptions(referenceItems, "classification", true).map((referenceItem) => ({
    count: items.filter((item) => item.classification === referenceItem.code).length,
    description: referenceItem.description ?? "",
    label: referenceItem.label,
    level: referenceItem.code,
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
