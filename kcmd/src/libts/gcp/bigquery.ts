// API client for BigQuery
//

import * as api from './api';
import * as context from './context';

/**
 * Represents a BigQuery dataset resource as returned by the BigQuery REST API.
 *
 * The index signature captures additional, dynamically-typed fields returned by
 * the API that are not explicitly modeled here; callers must narrow them before
 * use.
 */
export interface Dataset {
  id: string;
  datasetReference: {
    projectId: string;
    datasetId: string;
  };
  location: string;
  [key: string]: unknown;
}

/**
 * Represents a BigQuery table resource as returned by the BigQuery REST API.
 *
 * The index signature captures additional, dynamically-typed fields returned by
 * the API that are not explicitly modeled here; callers must narrow them before
 * use.
 */
export interface Table {
  id: string;
  tableReference: {
    projectId: string;
    datasetId: string;
    tableId: string;
  };
  [key: string]: unknown;
}

interface TableList {
  tables: Table[];
  nextPageToken?: string;
}

/**
 * Client for the BigQuery v2 REST API, providing typed access to dataset and
 * table resources.
 */
export class BigQueryClient extends api.ApiClient {
  constructor(ctx: context.ApiContext) {
    super('https://bigquery.googleapis.com', 'bigquery/v2', ctx);
  }

  async getDataset(
    project: string,
    dataset: string,
  ): Promise<api.ApiResult<Dataset>> {
    const name = `projects/${project}/datasets/${dataset}`;
    const params: Record<string, string | number> = {'datasetView': 'METADATA'};

    return await this._get(name, params);
  }

  async *listTables(project: string, dataset: string): AsyncGenerator<Table> {
    const name = `projects/${project}/datasets/${dataset}/tables`;

    let pageToken: string | undefined = undefined;
    do {
      const params: Record<string, string | number> = {'maxResults': 500};
      if (pageToken) {
        params['pageToken'] = pageToken;
      }

      const res = await this._get<TableList>(name, params);
      if (res.status !== 200) {
        throw new Error(`Failed to list tables: ${res.message || res.status}`);
      }

      const tables = res.result?.tables || [];
      for (const table of tables) {
        yield table;
      }

      pageToken = res.result?.nextPageToken;
    } while (pageToken);
  }
}
