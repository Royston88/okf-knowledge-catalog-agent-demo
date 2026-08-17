const fs = require('fs');
const path = require('path');

// Redirect stderr to a file for debugging
const logFile = fs.createWriteStream(path.join(__dirname, 'mcp_debug.log'), { flags: 'a' });
console.error = function(...args) {
    logFile.write(new Date().toISOString() + " " + args.join(' ') + '\n');
};
process.stderr.write = function(chunk, encoding, callback) {
    logFile.write(chunk, encoding, callback);
    return true;
};

console.error("--- Environment Debug ---");
console.error("PATH:", process.env.PATH);
console.error("HOME:", process.env.HOME);
console.error("GOOGLE_APPLICATION_CREDENTIALS:", process.env.GOOGLE_APPLICATION_CREDENTIALS);
console.error("GOOGLE_CLOUD_PROJECT:", process.env.GOOGLE_CLOUD_PROJECT);
console.error("-------------------------");

const { startServer } = require(path.join(__dirname, 'build/ts/tool/tool/mcp.js'));

process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
});
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Get workspace from args, default to '.'
const args = process.argv.slice(2);
let workspace = '.';
for (let i = 0; i < args.length; i++) {
    if (args[i] === '--workspace' && i + 1 < args.length) {
        workspace = args[i+1];
        break;
    }
}

console.error("Starting MCP server with workspace:", workspace);

startServer(workspace).then(() => {
    console.error("MCP server connected successfully.");
}).catch(err => {
    console.error("Failed to start MCP server:", err);
    process.exit(1);
});
