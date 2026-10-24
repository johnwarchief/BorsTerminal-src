import { createApp } from './bridge.js';
import * as appMod from './src/main.js';

let FRONTEND;
try {
  FRONTEND = decodeURIComponent(new URL('./frontend', import.meta.url).pathname);
  if (/^\/[A-Za-z]:\//.test(FRONTEND)) FRONTEND = FRONTEND.slice(1); // windows /C:/…
} catch { FRONTEND = tjs.exePath.replace(/[\\/][^\\/]*$/, '') + '/frontend'; }
const RESOURCES = null;
const EXECUTABLES = null;

const app = await createApp({
  htmlPath: FRONTEND + '/index.html',
  title: "BorsTerminal — TinyJS M2",
  size: "1360x760",
  version: "0.2.0",
  tinyjsVersion: "v0.65.0",
  id: "com.borsterminal.m2tinyjs",
  resourcesPath: RESOURCES,
  executablesPath: EXECUTABLES,
  api: appMod.api ?? {},
  onMenu: appMod.onMenu,
  onTray: appMod.onTray,
  onHotkey: appMod.onHotkey,
  onContextMenu: appMod.onContextMenu,
  onSystem: appMod.onSystem,
  onOpenUrl: appMod.onOpenUrl,
  onOpenFiles: appMod.onOpenFiles,
  onNotificationClick: appMod.onNotificationClick,
  onNotificationAction: appMod.onNotificationAction,
  onMediaKey: appMod.onMediaKey,
  onWindowClosed: appMod.onWindowClosed,
  onWindowState: appMod.onWindowState,
  onClipboardChange: appMod.onClipboardChange,
  onUpdateAvailable: appMod.onUpdateAvailable,
  onAudioTap: appMod.onAudioTap,
  onLocale: appMod.onLocale,
  onNavigate: appMod.onNavigate,
  onDownload: appMod.onDownload,
  onWindowOpen: appMod.onWindowOpen,
  url: null,
  downloads: "ask",
  popups: "window",
  apiAccess: null,
  inject: null,
  chrome: null,
  update: null,
  activation: "accessory",
  mainWindow: false,
  readAccess: null,
  userAgent: null,
  audioTap: null,
  windowPlacement: null,
  contextMenu: true,
  browserAccelerators: false,
  debug: false,
  about: null,
  urlScheme: null,
  fileExtensions: null,
  openFolders: false,
  permissions: null,
  offscreenRescue: null,
  rememberWindows: false,
});
if (appMod.init) appMod.init(app);

const launcherSt = await app.done;
if (launcherSt?.term_signal || launcherSt?.exit_status) {
  console.error('tinyjs: webview launcher ' + (launcherSt.term_signal
    ? 'killed by ' + launcherSt.term_signal
    : 'exited with status ' + launcherSt.exit_status));
  tjs.exit(launcherSt.exit_status || 1);
}
tjs.exit(0);
