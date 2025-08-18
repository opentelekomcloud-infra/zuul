const rewiredEsbuild = require("react-app-rewired-esbuild");

module.exports = function override(config, env) {
  // Use esbuild for our source code
  config = rewiredEsbuild()(config, env);

  // Force webpack to prefer CommonJS over ES modules for problematic packages
  config.resolve.mainFields = ['browser', 'main', 'module'];

  // Add aliases to force CommonJS versions of problematic packages
  config.resolve.alias = {
    ...config.resolve.alias,
    'swagger-client/es': 'swagger-client/lib',
    '@swagger-api/apidom-reference/configuration/empty': '@swagger-api/apidom-reference/src/configuration/empty.cjs',
  };

  // Find the oneOf rule that contains the file type rules
  const oneOfRule = config.module.rules.find(rule => rule.oneOf);

  if (oneOfRule) {
    // Add a rule to handle Victory.js, swagger-ui, and ApiDOM modules with Babel before esbuild
    oneOfRule.oneOf.unshift({
      test: /\.jsx?$/,
      include: /node_modules\/(victory-|@patternfly\/react-charts|swagger-ui|swagger-client|@swagger-api)/,
      exclude: /node_modules\/(?!(victory-|@patternfly\/react-charts|swagger-ui|swagger-client|@swagger-api))/,
      use: {
        loader: require.resolve('babel-loader'),
        options: {
          cacheDirectory: true,
          cacheCompression: false,
          presets: [
            [require.resolve('@babel/preset-env'), {
              targets: {
                browsers: ["last 1 version", "> 1%", "maintained node versions", "not dead"]
              }
            }],
            [require.resolve('@babel/preset-react'), { runtime: 'automatic' }]
          ],
          plugins: [
            require.resolve('@babel/plugin-transform-class-properties'),
            require.resolve('@babel/plugin-transform-optional-chaining'),
            require.resolve('@babel/plugin-transform-nullish-coalescing-operator')
          ]
        }
      }
    });
  }

  return config;
};
