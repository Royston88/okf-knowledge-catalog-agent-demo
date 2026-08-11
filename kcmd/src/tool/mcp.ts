// MCP Server implementation
//

import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {z} from 'zod';

import * as kcmd from '../libts';
import * as gcp from '../libts/gcp';

/**
 * Starts the kcmd MCP (Model Context Protocol) server over stdio.
 *
 * Registers the catalog tools (list-entries, lookup-entry, modify-entry) backed
 * by a catalog snapshot loaded from the given base path, then connects the
 * server to a stdio transport so it can serve MCP requests.
 *
 * @param basePath The filesystem path from which to load the catalog snapshot.
 *     Defaults to the current directory.
 */
export async function startServer(basePath = '.'): Promise<void> {
  const server = new McpServer({
    name: 'kcmd',
    version: '1.0.0',
  });

  const ctx = gcp.ApiContext.default();
  const snapshot = await kcmd.CatalogSnapshot.fromPath(basePath, ctx);

  server.registerTool(
    'list-entries',
    {
      description:
        'List names of all catalog entries. ' +
        'Each entry corresponds to a resource that has associated metadata.',
    },
    async () => {
      const names = await snapshot.listEntries();
      return {
        content: [{type: 'text', text: JSON.stringify(names, null, 2)}],
      };
    },
  );

  server.registerTool(
    'lookup-entry',
    {
      description: 'Lookup the metadata of a specific catalog entry by name',
      inputSchema: {
        name: z.string().describe('The name of the entry to lookup'),
      },
    },
    async ({name}) => {
      try {
        const entry = await snapshot.lookupEntry(name);
        return {
          content: [{type: 'text', text: JSON.stringify(entry, null, 2)}],
        };
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          isError: true,
          content: [{type: 'text', text: `Error looking up entry: ${message}`}],
        };
      }
    },
  );

  server.registerTool(
    'modify-entry',
    {
      description:
        'Modify (either "resource" or an aspect key field) of a catalog entry by name',
      inputSchema: {
        name: z.string().describe('The name of the entry to modify'),
        field: z
          .string()
          .describe(
            'The name of the field being updated. Either "resource" or an aspect key',
          ),
        updates: z
          .record(z.string(), z.any())
          .describe('A structured JSON data dictionary containing the updates'),
      },
    },
    async ({name, field, updates}) => {
      try {
        const existingEntry = await snapshot.lookupEntry(name);
        let updatedEntry: kcmd.Entry = {
          name,
          type: existingEntry.type,
          resource: field === 'resource' ? updates : {},
          aspects: field !== 'resource' ? {[field]: updates} : undefined,
        };

        await snapshot.updateEntry(updatedEntry, [field]);

        updatedEntry = await snapshot.lookupEntry(name);
        return {
          content: [
            {type: 'text', text: JSON.stringify(updatedEntry, null, 2)},
          ],
        };
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          isError: true,
          content: [{type: 'text', text: `Error modifying entry: ${message}`}],
        };
      }
    },
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
}
