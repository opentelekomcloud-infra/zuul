import { defineConfig } from 'vite'
import path from 'path';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  return {
    // base defaults to /; change it to '' so that index.html
    // references "assets/..." instead of "/asserts/..." so that it
    // will work in our static hosting configuration.
    base: '',
    envPrefix: 'REACT_APP',
    test: {
      globals: true,
      environment: 'jsdom',
    },
    resolve: {
      alias: {
        'store': mode === 'production'
        // eslint-disable-next-line no-undef
          ? path.resolve(__dirname, './src/store.prod')
        // eslint-disable-next-line no-undef
          : path.resolve(__dirname, './src/store.dev')
      }
    },
  }
})
