const rewiredEsbuild = require("react-app-rewired-esbuild");

module.exports = function override(config, env) {
  // Use esbuild to transpile the code
  config = rewiredEsbuild()(config, env);

  // Transpile Xterm.js since it ships UMD code which we cannot
  // use directly in our ES6 modules.
  config.module.rules.push({
    test: /\.js$/,
    include: /node_modules\/@xterm/,
    use: {
      loader: require.resolve('esbuild-loader'),
      options: {
        loader: 'js',
        target: 'es2015',
      },
    },
  });

  return config;
};
