import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.evove.app',
  appName: 'Evove',
  webDir: 'dist',
  // The web app is black by design (src/app.css), so the WebView itself starts
  // black instead of the default white, which would flash on every cold start.
  backgroundColor: '#000000',
};

export default config;
