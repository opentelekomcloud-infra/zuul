const rewiredEsbuild = require("react-app-rewired-esbuild");

module.exports = function override(config, env) {
  // Use esbuild for our source code
  config = rewiredEsbuild()(config, env);
  
  // Find the oneOf rule that contains the file type rules
  const oneOfRule = config.module.rules.find(rule => rule.oneOf);
  
  if (oneOfRule) {
    // Add a rule to handle Victory.js modules with Babel before esbuild
    oneOfRule.oneOf.unshift({
      test: /\.jsx?$/,
      include: /node_modules\/(victory-|@patternfly\/react-charts)/,
      exclude: /node_modules\/(?!(victory-|@patternfly\/react-charts))/,
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
