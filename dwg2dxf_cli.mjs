#!/usr/bin/env node
/**
 * DWG→DXF converter using @mlightcad/libredwg-web v0.7.7
 * Usage: node dwg2dxf_cli.mjs <input.dwg> <output.dxf>
 *
 * Bundled files: wasm_bundle/libredwg-web.wasm, wasm_bundle/libredwg-web.js
 * Falls back to node_modules for development.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function findWasmFiles() {
    // Try bundled path first (PyInstaller), then node_modules (dev)
    const bundled = path.join(__dirname, 'wasm_bundle');
    const npm = path.join(__dirname, 'node_modules', '@mlightcad', 'libredwg-web', 'wasm');

    for (const base of [bundled, npm]) {
        const wasm = path.join(base, 'libredwg-web.wasm');
        const js = path.join(base, 'libredwg-web.js');
        if (fs.existsSync(wasm) && fs.existsSync(js)) {
            return { wasm, js };
        }
    }
    throw new Error('WASM files not found. Reinstall with: npm install @mlightcad/libredwg-web');
}

async function main() {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('Usage: node dwg2dxf_cli.mjs <input.dwg> <output.dxf>');
        process.exit(1);
    }

    const [inputPath, outputPath] = args;
    const inputAbs = path.resolve(inputPath);
    const outputAbs = path.resolve(outputPath);

    if (!fs.existsSync(inputAbs)) {
        console.error('Input file not found:', inputAbs);
        process.exit(1);
    }

    const { wasm: wasmPath, js: jsPath } = findWasmFiles();
    const dwgData = fs.readFileSync(inputAbs);
    const wasmBinary = fs.readFileSync(wasmPath);

    // Import WASM glue (file:// URL for Windows ESM compatibility)
    const jsUrl = 'file:///' + path.resolve(jsPath).replace(/\\/g, '/');
    const { default: createModule } = await import(jsUrl);

    const Module = await createModule({
        wasmBinary,
        arguments: [],
        noExitRuntime: true,
        print: () => {},
        printErr: () => {},
    });

    // Write DWG to virtual FS, call dwg_write_dxf (takes std::string)
    Module.FS.writeFile('/input.dwg', dwgData);
    const rc = Module.dwg_write_dxf('/input.dwg', '/output.dxf');

    if (rc !== 0) {
        console.error('Conversion failed (code ' + rc + '). DWG may be corrupted or unsupported.');
        process.exit(1);
    }

    const dxfData = Module.FS.readFile('/output.dxf', { encoding: 'binary' });
    fs.writeFileSync(outputAbs, Buffer.from(dxfData));
    console.log(outputAbs);
}

main().catch(err => {
    console.error('FATAL:', err.message);
    process.exit(1);
});
