export interface RouteConfig {
  id: string;
  /** Short all-caps identifier shown as the panel heading. */
  name: string;
  /** Full API name shown as the subtitle. */
  label: string;
  /** One-line explanation of what this API returns. */
  description: string;
  /** Short API method type shown as a badge in the panel header. */
  method: string;
  /** Data sources this API draws from. */
  dataSources: string[];
  color: string;
  glowColor: string;
  dimColor: string;
  endpoint: string;
}

export const ROUTES: RouteConfig[] = [
  {
    id: 'copilot',
    name: 'COPILOT CHAT',
    label: 'Microsoft Copilot Chat API',
    description: 'AI-synthesized answer grounded in your M365 data',
    method: 'LLM Synthesis',
    dataSources: ['Emails', 'Calendar', 'Teams', 'SharePoint', 'OneDrive', 'Connectors', 'People', 'Web'],
    color: '#00d4ff',
    glowColor: 'rgba(0, 212, 255, 0.22)',
    dimColor: 'rgba(0, 212, 255, 0.07)',
    endpoint: '/api/v1/copilot_chat',
  },
  {
    id: 'retrieval',
    name: 'RETRIEVAL API',
    label: 'M365 Copilot Retrieval API',
    description: 'Raw semantic chunks retrieved from SharePoint & OneDrive',
    method: 'Semantic Retrieval',
    dataSources: ['SharePoint', 'OneDrive', 'Connectors'],
    color: '#ff6b35',
    glowColor: 'rgba(255, 107, 53, 0.22)',
    dimColor: 'rgba(255, 107, 53, 0.07)',
    endpoint: '/api/v1/retrieval_api',
  },
  {
    id: 'graph',
    name: 'GRAPH API',
    label: 'Microsoft Graph API',
    description: 'Raw M365 data — emails, calendar, Teams, files & people',
    method: 'Direct Data',
    dataSources: ['Emails', 'Calendar', 'Teams', 'OneDrive', 'SharePoint', 'People'],
    color: '#a855f7',
    glowColor: 'rgba(168, 85, 247, 0.22)',
    dimColor: 'rgba(168, 85, 247, 0.07)',
    endpoint: '/api/v1/graph_api',
  },
];
