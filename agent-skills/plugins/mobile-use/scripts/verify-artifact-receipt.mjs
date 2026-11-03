#!/usr/bin/env node

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCHEMA_VERSION = 1;
const MAX_RECEIPT_BYTES = 8 * 1024 * 1024;

export async function verifyArtifactReceipt(receiptPath) {
  const absoluteReceiptPath = resolve(receiptPath);
  let receiptStat;
  try {
    receiptStat = await stat(absoluteReceiptPath);
  } catch (error) {
    throw verifierError(
      "artifact.receipt.unreadable",
      `Unable to read receipt: ${error instanceof Error ? error.message : String(error)}`,
      2,
    );
  }
  if (!receiptStat.isFile()) throw verifierError("artifact.receipt.invalid", "Receipt path is not a file.", 2);
  if (receiptStat.size > MAX_RECEIPT_BYTES) {
    throw verifierError("artifact.receipt.too-large", "Receipt exceeds the 8 MiB limit.", 2);
  }

  let payload;
  try {
    payload = JSON.parse(await readFile(absoluteReceiptPath, "utf8"));
  } catch (error) {
    throw verifierError(
      "artifact.receipt.invalid-json",
      `Unable to parse receipt JSON: ${error instanceof Error ? error.message : String(error)}`,
      2,
    );
  }

  if (!isRecord(payload)) throw verifierError("artifact.receipt.invalid", "Receipt JSON must be an object.", 2);

  const descriptors = collectArtifactDescriptors(payload);
  if (descriptors.length === 0) {
    throw verifierError("artifact.receipt.missing-artifact", "No SHA-256 artifact descriptor was found.", 2);
  }

  const artifacts = [];
  for (const descriptor of descriptors) artifacts.push(await verifyDescriptor(descriptor));

  const hasMismatch = artifacts.some((artifact) => artifact.integrity === "mismatch");
  const hasUnavailable = artifacts.some((artifact) => artifact.integrity === "unavailable");
  const exitCode = hasMismatch ? 4 : hasUnavailable ? 3 : 0;

  return Object.freeze({
    schemaVersion: SCHEMA_VERSION,
    ok: exitCode === 0,
    commandOk: typeof payload.ok === "boolean" ? payload.ok : null,
    receipt: absoluteReceiptPath,
    visualInspection: false,
    artifacts: Object.freeze(artifacts),
    exitCode,
  });
}

function collectArtifactDescriptors(payload) {
  const found = new Map();
  const pending = [payload];
  const visited = new Set();

  while (pending.length > 0) {
    const value = pending.pop();
    if (!value || typeof value !== "object" || visited.has(value)) continue;
    visited.add(value);

    if (isArtifactDescriptor(value)) {
      const key = `${value.uri}\n${value.digest}\n${value.size}`;
      if (!found.has(key)) found.set(key, Object.freeze({
        algorithm: value.algorithm,
        digest: value.digest.toLowerCase(),
        mediaType: typeof value.mediaType === "string" ? value.mediaType : undefined,
        size: value.size,
        uri: value.uri,
      }));
    }

    if (Array.isArray(value)) pending.push(...value);
    else pending.push(...Object.values(value));
  }

  return [...found.values()];
}

async function verifyDescriptor(descriptor) {
  if (!descriptor.uri.startsWith("file:")) {
    return Object.freeze({
      ...descriptor,
      integrity: "unavailable",
      reason: "Only local file: artifact URIs can be verified.",
    });
  }

  let artifactPath;
  try {
    artifactPath = fileURLToPath(descriptor.uri);
  } catch (error) {
    return Object.freeze({
      ...descriptor,
      integrity: "unavailable",
      reason: `Invalid file URI: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
  if (!isAbsolute(artifactPath)) {
    return Object.freeze({ ...descriptor, integrity: "unavailable", reason: "Artifact path is not absolute." });
  }

  try {
    const artifactStat = await stat(artifactPath);
    if (!artifactStat.isFile()) {
      return Object.freeze({ ...descriptor, path: artifactPath, integrity: "unavailable", reason: "Artifact is not a file." });
    }
    const actualDigest = await sha256File(artifactPath);
    const sizeMatches = artifactStat.size === descriptor.size;
    const digestMatches = actualDigest === descriptor.digest;
    return Object.freeze({
      ...descriptor,
      path: artifactPath,
      actualSize: artifactStat.size,
      actualDigest,
      sizeMatches,
      digestMatches,
      integrity: sizeMatches && digestMatches ? "verified" : "mismatch",
    });
  } catch (error) {
    return Object.freeze({
      ...descriptor,
      path: artifactPath,
      integrity: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    });
  }
}

function sha256File(filePath) {
  return new Promise((resolveDigest, rejectDigest) => {
    const hash = createHash("sha256");
    const stream = createReadStream(filePath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.once("error", rejectDigest);
    stream.once("end", () => resolveDigest(hash.digest("hex")));
  });
}

function isArtifactDescriptor(value) {
  return isRecord(value)
    && value.algorithm === "sha256"
    && typeof value.digest === "string"
    && /^[0-9a-f]{64}$/iu.test(value.digest)
    && Number.isSafeInteger(value.size)
    && value.size >= 0
    && typeof value.uri === "string";
}

function verifierError(code, message, exitCode) {
  const error = new Error(message);
  error.code = code;
  error.exitCode = exitCode;
  return error;
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function main(argv) {
  if (argv.length !== 1 || argv[0] === "--help" || argv[0] === "-h") {
    const help = "Usage: verify-artifact-receipt.mjs /absolute/path/to/mobile-use-receipt.json";
    if (argv[0] === "--help" || argv[0] === "-h") {
      process.stdout.write(`${help}\n`);
      return 0;
    }
    throw verifierError("artifact.cli.argument", help, 2);
  }

  const result = await verifyArtifactReceipt(argv[0]);
  process.stdout.write(`${JSON.stringify(result)}\n`);
  return result.exitCode;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`${JSON.stringify({
      schemaVersion: SCHEMA_VERSION,
      ok: false,
      error: {
        code: typeof error?.code === "string" ? error.code : "artifact.verification.failed",
        message: error instanceof Error ? error.message : String(error),
      },
    })}\n`);
    process.exitCode = Number.isInteger(error?.exitCode) ? error.exitCode : 1;
  }
}
