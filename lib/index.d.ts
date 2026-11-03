export interface ResearchReportPluginConfig {
  pythonExecutable?: string;
}

export declare const name: string;
export declare const SKILL_DIR: string;
export declare const SCRIPTS_DIR: string;
export declare function apply(ctx: any, config?: ResearchReportPluginConfig): void;
