import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.evove.app',
  appName: 'Evove',
  webDir: 'dist',
  // The web app is black by design (src/app.css), so the WebView itself starts
  // black instead of the default white, which would flash on every cold start.
  backgroundColor: '#000000',
  android: {
    // The bundle is served from https://localhost inside the WebView, so a call
    // to the dev API over plain http counts as mixed content and the WebView
    // blocks it. Drop this once the API answers over HTTPS; cleartext traffic is
    // already debug-only, in android/app/src/debug/AndroidManifest.xml.
    allowMixedContent: true,
  },
};

export default config;
