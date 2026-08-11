// API Client base class
//

import * as context from './context';

/**
 * Outcome of a single GCP API request. Carries the HTTP status code, the parsed
 * response body on success (`result`), or the raw error text on failure
 * (`message`).
 */
export interface ApiResult<T> {
  status: number;
  result?: T;
  message?: string;
}

/**
 * A primitive value (or array of primitives) that can appear as a query-string
 * parameter. Each value is serialized via `String(...)` when building the URL.
 */
type QueryParamValue =
  | string
  | number
  | boolean
  | Array<string | number | boolean>;

/** Map of query-string parameter names to their values. */
type QueryParams = Record<string, QueryParamValue | undefined>;

/**
 * Request payload for write operations (POST/PATCH). It is an arbitrary
 * JSON-serializable value that is passed through to `JSON.stringify`, so its
 * shape is not known at this layer.
 */
type RequestBody = unknown;

/** Options passed to the low-level fetch wrapper. */
interface RequestOptions {
  method: string;
  body?: RequestBody;
  headers?: Record<string, string>;
}

/**
 * Thin base class for GCP REST API clients. Builds request URLs from an
 * endpoint, path prefix, and resource name, attaches authentication headers
 * from the supplied {@link context.ApiContext}, and transparently retries once
 * after refreshing the token on a 401 response.
 */
export class ApiClient {
  private readonly _endpoint: string;
  private readonly _pathPrefix: string;
  private readonly _context: context.ApiContext;

  constructor(
    endpoint: string,
    pathPrefix: string,
    context: context.ApiContext,
  ) {
    this._endpoint = endpoint;
    this._pathPrefix = pathPrefix;
    this._context = context;
  }

  get context(): context.ApiContext {
    return this._context;
  }

  async _get<T>(
    resourceName: string,
    queryParams?: QueryParams,
  ): Promise<ApiResult<T>> {
    const url = `${this._endpoint}/${this._pathPrefix}/${resourceName}`;
    return this._requestRetry('GET', url, queryParams);
  }

  async _post<T>(
    resourceName: string,
    body: RequestBody,
    queryParams?: QueryParams,
  ): Promise<ApiResult<T>> {
    const url = `${this._endpoint}/${this._pathPrefix}/${resourceName}`;
    return this._requestRetry('POST', url, queryParams, body);
  }

  async _patch<T>(
    resourceName: string,
    body: RequestBody,
    queryParams?: QueryParams,
  ): Promise<ApiResult<T>> {
    const url = `${this._endpoint}/${this._pathPrefix}/${resourceName}`;
    return this._requestRetry('PATCH', url, queryParams, body);
  }

  async _delete<T>(
    resourceName: string,
    queryParams?: QueryParams,
  ): Promise<ApiResult<T>> {
    const url = `${this._endpoint}/${this._pathPrefix}/${resourceName}`;
    return this._requestRetry('DELETE', url, queryParams);
  }

  private async _requestRetry<T>(
    method: string,
    url: string,
    queryParams?: QueryParams,
    body?: RequestBody,
  ): Promise<ApiResult<T>> {
    if (queryParams) {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(queryParams)) {
        if (value !== undefined) {
          if (Array.isArray(value)) {
            value.forEach((v) => params.append(key, String(v)));
          } else {
            params.append(key, String(value));
          }
        }
      }
      const queryString = params.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }

    this._context.log(`${method} ${url}{body ? '\n' : ''}`, body);

    let response = await this._requestCore(url, {method, body});
    if (response.status === 401) {
      this.context.refresh();
      response = await this._requestCore(url, {method, body});
    }

    const result: ApiResult<T> = {status: response.status};
    if (!response.ok) {
      result.message = await response.text();
    } else {
      result.result = (await response.json()) as T;
    }

    this._context.log(
      `${response.status}:${result.message ?? ''}\n`,
      result.result,
    );
    return result;
  }

  private async _requestCore(
    url: string,
    options: RequestOptions,
  ): Promise<Response> {
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${this._context.token}`,
      'Content-Type': 'application/json',
    };

    return fetch(url, {
      ...options,
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  }
}
