import { mount } from 'svelte'
import { Capacitor } from '@capacitor/core'
import './app.css'
import App from './App.svelte'

// Inside the Android shell, app.css scales the whole interface up a notch.
if (Capacitor.isNativePlatform()) document.documentElement.classList.add('native')

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
