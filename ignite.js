#!/usr/bin/env node

/**
 * Aetherlink Quantum Ignition Key System (QIKS)
 * Phase 1: APK build trigger and signer (local scaffold)
 */

const { exec } = require('child_process');
const path = require('path');

// Project details
const PROJECT_DIR = path.join(__dirname, 'AetherlinkMobile');
const BUILD_COMMAND = 'eas build -p android --profile preview';

// Launch build
console.log("Initializing Aetherlink Quantum Ignition Key System...");
console.log("Triggering secure APK build...");

exec(BUILD_COMMAND, { cwd: PROJECT_DIR }, (error, stdout, stderr) => {
    if (error) {
        console.error("Build failed:", error.message);
        return;
    }
    if (stderr) {
        console.error("Warnings:", stderr);
    }
    console.log("Build output:", stdout);
    console.log("Build initiated. Monitor Expo dashboard for progress.");
});
