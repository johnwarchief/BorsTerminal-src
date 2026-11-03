#!/usr/bin/env node

import { runCli } from "../../../bin/mobile-use.mjs";

process.exitCode = await runCli(process.argv.slice(2));
