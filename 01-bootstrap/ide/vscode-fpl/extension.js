// Starts the FPL language server (ide/fpl-ls) for .fpl files. Untested in VS Code itself.
const vscode = require("vscode");
const { LanguageClient } = require("vscode-languageclient/node");
let client;
exports.activate = () => {
  const command = vscode.workspace.getConfiguration("fpl").get("server");
  client = new LanguageClient("fpl", "FPL", { command, args: [] }, { documentSelector: [{ language: "fpl" }] });
  return client.start();
};
exports.deactivate = () => client && client.stop();
