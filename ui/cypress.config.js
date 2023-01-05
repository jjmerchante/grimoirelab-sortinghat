const { defineConfig } = require("cypress");

module.exports = defineConfig({
  e2e: {
    baseUrl: "http://localhost:8000",
    screenshotOnRunFailure: true,
    specPattern: "tests/e2e/specs/**/*.cy.{js,jsx,ts,tsx}",
    supportFile: "tests/e2e/support/index.js",
    defaultCommandTimeout: 100000,
    pageLoadTimeout: 100000,
    requestTimeout: 100000,
    video: true,
    projectId: "izzmv6"
  }
});
