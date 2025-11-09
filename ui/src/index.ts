// Main CRM Framework Exports
export { CrmShell, PipelineView, RecordView, AutomationsView } from './crm-lib';

// Vertical CRM Apps
export { default as PeakProCRM } from './verticals/PeakProCRM';
export { default as PolicyPalCRM } from './verticals/PolicyPalCRM';

// Types
export interface BundleData {
    status: any;
    federation: any;
    opt: any;
    learn: any;
    policies: any;
    alerts: any[];
}

export interface AutomationRule {
    id: string;
    name: string;
    trigger: {
        event: string;
        conditions: any[];
    };
    actions: any[];
    enabled: boolean;
}