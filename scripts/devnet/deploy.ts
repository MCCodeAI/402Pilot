/**
 * 402Pilot — deploy MockUSDC + X402Facilitator to a local Anvil fork.
 *
 * Run:
 *   pnpm dlx tsx scripts/devnet/deploy.ts          (or)
 *   npx tsx scripts/devnet/deploy.ts
 *
 * Prereqs:
 *   1. anvil running on $RPC_URL  (./scripts/devnet/start_anvil.sh)
 *   2. solc installed and on $PATH (so we can compile facilitator.sol)
 *   3. viem and tsx in node_modules (typically inside viz/, but you can
 *      also run `npm i -g tsx viem` once)
 *
 * On success the script writes a `deployments.json` next to itself
 * containing the addresses, which the viz can read at runtime.
 */
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  createWalletClient,
  createPublicClient,
  http,
  parseAbi,
  type Hex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";

const __dirname = dirname(fileURLToPath(import.meta.url));

const RPC_URL = process.env.RPC_URL ?? "http://127.0.0.1:8545";

// Anvil's first deterministic dev key (DO NOT use elsewhere).
const DEV_PK: Hex =
  (process.env.DEV_PRIVATE_KEY as Hex) ??
  "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";

interface CompiledArtifact {
  abi: unknown[];
  bytecode: Hex;
}

function compile(source: string, contractName: string): CompiledArtifact {
  const sol = JSON.stringify({
    language: "Solidity",
    sources: { "facilitator.sol": { content: source } },
    settings: {
      outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
      optimizer: { enabled: true, runs: 200 },
    },
  });
  const out = execSync("solc --standard-json", { input: sol }).toString();
  const json = JSON.parse(out) as {
    contracts: {
      "facilitator.sol": Record<
        string,
        { abi: unknown[]; evm: { bytecode: { object: string } } }
      >;
    };
    errors?: { severity: string; formattedMessage: string }[];
  };
  if (json.errors) {
    const fatals = json.errors.filter((e) => e.severity === "error");
    if (fatals.length > 0) {
      throw new Error(
        "solc errors:\n" + fatals.map((e) => e.formattedMessage).join("\n")
      );
    }
  }
  const c = json.contracts["facilitator.sol"][contractName];
  return { abi: c.abi, bytecode: ("0x" + c.evm.bytecode.object) as Hex };
}

async function main() {
  const source = readFileSync(
    join(__dirname, "deploy_facilitator.sol"),
    "utf8"
  );
  const usdc = compile(source, "MockUSDC");
  const fac = compile(source, "X402Facilitator");

  const account = privateKeyToAccount(DEV_PK);
  const wallet = createWalletClient({ account, transport: http(RPC_URL) });
  const pub = createPublicClient({ transport: http(RPC_URL) });

  console.log("Deploying MockUSDC...");
  const usdcHash = await wallet.deployContract({
    abi: usdc.abi as never,
    bytecode: usdc.bytecode,
    chain: null,
    args: [],
  });
  const usdcRcpt = await pub.waitForTransactionReceipt({ hash: usdcHash });
  const usdcAddr = usdcRcpt.contractAddress!;
  console.log("  USDC at", usdcAddr);

  // Receiver = arbitrary distinct address (anvil default acct[1])
  const receiver: Hex = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";

  console.log("Deploying X402Facilitator...");
  const facHash = await wallet.deployContract({
    abi: fac.abi as never,
    bytecode: fac.bytecode,
    chain: null,
    args: [usdcAddr, receiver],
  });
  const facRcpt = await pub.waitForTransactionReceipt({ hash: facHash });
  const facAddr = facRcpt.contractAddress!;
  console.log("  Facilitator at", facAddr);

  // Mint some USDC to the dev account so it can settle calls
  const mintAbi = parseAbi(["function mint(address,uint256)"]);
  await wallet.writeContract({
    address: usdcAddr,
    abi: mintAbi,
    functionName: "mint",
    args: [account.address, 1_000_000_000n], // 1,000 USDC at 6 decimals
    chain: null,
  });

  const out = {
    rpc: RPC_URL,
    usdc: usdcAddr,
    facilitator: facAddr,
    receiver,
    deployer: account.address,
    deployed_at: new Date().toISOString(),
  };
  writeFileSync(
    join(__dirname, "deployments.json"),
    JSON.stringify(out, null, 2)
  );
  console.log("\nWrote deployments.json:");
  console.log(out);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
