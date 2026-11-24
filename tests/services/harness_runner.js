'use strict';

async function run(scenarios) {
    const available = Object.keys(scenarios);
    const args = process.argv.slice(2);
    if (args.length === 1 && args[0] === '--list') {
        console.log(JSON.stringify(available));
        return;
    }
    const selected = args.length ? args : (process.env.FC_NODE_SCENARIOS || '').split(/[\s,]+/).filter(Boolean);
    const names = selected.length ? selected : available;
    const unknown = names.filter(name => !Object.hasOwn(scenarios, name));
    const ran = [];
    const failed = [];
    if (unknown.length) {
        console.error(`unknown scenarios: ${unknown.join(', ')}; available: ${available.join(', ')}`);
        failed.push(...unknown);
        process.exitCode = 2;
    } else {
        for (const name of names) {
            ran.push(name);
            try {
                await scenarios[name]();
            } catch (error) {
                failed.push(name);
                console.error(`scenario ${name} failed\n${error.stack || error}`);
            }
        }
        if (failed.length) process.exitCode = 1;
    }
    console.log(JSON.stringify({ ran, failed }));
}

module.exports = { run };
