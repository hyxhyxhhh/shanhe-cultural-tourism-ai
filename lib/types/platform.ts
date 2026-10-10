export interface StatItem { label: string; value: string; note?: string }
export interface InsightItem { icon?: string; label: string; value?: string; note?: string; status?: string }
export interface PageSection { title: string; subtitle?: string; action?: string; items: InsightItem[] }

export interface DomainPageData {
  title: string;
  description: string;
  eyebrow?: string;
  heroTitle: string;
  heroDescription: string;
  stats?: StatItem[];
  sections: PageSection[];
}

export interface ProfessionalAgentData {
  id: string;
  title: string;
  description: string;
  target: string;
  version: string;
  phases: string[];
  fields: Array<{ label: string; value: string }>;
  stats: StatItem[];
  evidence: InsightItem[];
  outputs: InsightItem[];
  automations: InsightItem[];
}
