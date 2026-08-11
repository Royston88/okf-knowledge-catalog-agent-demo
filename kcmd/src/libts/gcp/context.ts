// Context variables for GCP API requests
//

import * as cp from 'child_process';

const GCLOUD_PROJECT_CMD = 'gcloud -q config get-value project';
const GCLOUD_LOCATION_CMD = 'gcloud -q config get-value compute/region';
const GCLOUD_TOKEN_CMD =
  'gcloud -q auth application-default print-access-token';

/**
 * Holds the per-request GCP API context: the resolved project, location, and
 * access token used to authenticate calls to Google Cloud APIs. Provides a
 * factory that derives these values from the local gcloud configuration and a
 * helper to refresh the access token.
 */
export class ApiContext {
  readonly project: string;
  readonly location: string;
  private _token: string;

  constructor(project: string, location: string, token: string) {
    this.project = project;
    this.location = location;
    this._token = token;
  }

  get token(): string {
    return this._token;
  }

  log(message: string, data?: unknown) {
    if (process.env['GCP_LOG']) {
      console.log(`[GCP_LOG] ${message}`, data ? JSON.stringify(data) : '');
    }
  }

  static default(): ApiContext {
    // Prefer a caller-supplied token. google-cloud-sdk is absent from some
    // runtimes this CLI runs in -- Guitar/Borg workers and the Vertex Agent
    // Engine -- where every `gcloud` call below dies with "gcloud: command not
    // found", and callers see "No table entries pulled". The enrichment agent
    // mints a bearer token itself and passes it through this env var; see
    // kcmd_tools._run and //cloud/dataplex/context_success/agents/enrichment/
    // auth:borg_credentials.
    const envCtx = ApiContext.fromEnv();
    if (envCtx) {
      return envCtx;
    }

    // Creates an ApiContext instance using gcloud configuration

    const project = cp.execSync(GCLOUD_PROJECT_CMD).toString().trim();
    const location = cp.execSync(GCLOUD_LOCATION_CMD).toString().trim();
    const token = cp.execSync(GCLOUD_TOKEN_CMD).toString().trim();
    if (!project || !location || !token) {
      throw new Error(
        'Unable to retrieve project, location, or token. Ensure gcloud is configured.',
      );
    }

    return new ApiContext(project, location, token);
  }

  /** ApiContext from KCMD_ACCESS_TOKEN + GOOGLE_CLOUD_*, or null if unset. */
  private static fromEnv(): ApiContext | null {
    const token = process.env['KCMD_ACCESS_TOKEN'];
    const project = process.env['GOOGLE_CLOUD_PROJECT'];
    if (!token || !project) {
      return null;
    }
    const location = process.env['GOOGLE_CLOUD_LOCATION'] || 'global';
    return new ApiContext(project, location, token);
  }

  refresh() {
    // An injected token is owned by the caller and cannot be refreshed here
    // (there is no gcloud to refresh it with); keep using it.
    const token = process.env['KCMD_ACCESS_TOKEN'];
    if (token) {
      this._token = token;
      return;
    }
    this._token = cp.execSync(GCLOUD_TOKEN_CMD).toString().trim();
  }
}
