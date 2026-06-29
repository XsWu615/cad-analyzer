#!/usr/bin/env node
/**
 * CLI wrapper: LibreDWG WASM dwg2dxf.
 * Usage: node dwg2dxf_cli.mjs <input.dwg> <output.dxf>
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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

    const dwgData = fs.readFileSync(inputAbs);
    const wasmPath = path.join(__dirname, 'dwg2dxf.wasm');
    const wasmBinary = fs.readFileSync(wasmPath);

    const createModule = (await import('./dwg2dxf_wasm.mjs')).default;

    const Module = await createModule({
        wasmBinary,
        arguments: [],
        noExitRuntime: true,
        print: () => {},
        printErr: () => {},
    });

    // Write DWG to virtual FS
    Module.FS.writeFile('/input.dwg', dwgData);

    // Write C strings to HEAP at a safe region (after static data, before stack)
    const HEAP = Module.HEAPU8;
    const SAFE_OFFSET = 1024;  // past zero-init BSS region

    function writeCStr(offset, str) {
        const buf = Buffer.from(str + '\0', 'utf-8');
        for (let i = 0; i < buf.length; i++) HEAP[offset + i] = buf[i];
    }

    const IN_OFFSET = SAFE_OFFSET;
    const OUT_OFFSET = SAFE_OFFSET + 256;
    writeCStr(IN_OFFSET, '/input.dwg');
    writeCStr(OUT_OFFSET, '/output.dxf');

    const rc = Module._dwg2dxf(IN_OFFSET, OUT_OFFSET);

    if (rc !== 0) {
        console.error('Conversion failed (code ' + rc + '). File may not be a valid DWG.');
        process.exit(1);
    }

    try {
        const dxfData = Module.FS.readFile('/output.dxf', { encoding: 'binary' });
        fs.writeFileSync(outputAbs, Buffer.from(dxfData));
        console.log(outputAbs);
    } catch (e) {
        console.error('No output produced.');
        process.exit(1);
    }
}

main().catch(err => {
    console.error('FATAL:', err.message);
    process.exit(1);
});
