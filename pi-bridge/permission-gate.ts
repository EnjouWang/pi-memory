/**
 * Permission Gate（強化版）— demo / 開發時的安全閘門
 *
 * Pi 預設 YOLO 執行 bash；官方範例的 permission-gate 只攔 rm -rf / sudo / chmod 777，
 * 攔不到像 `pnpm install` 這種失控空轉。本檔在 agent 實際執行 **每一條 bash 指令前**
 * 先跳出 Yes / No 讓使用者同意，避免本地小模型亂下指令。
 *
 * 用法（與記憶 bridge 一起載入，順序不限）：
 *   PYTHONPATH=. pi -e ./pi-bridge/extension.ts -e ./pi-bridge/permission-gate.ts
 *
 * - 選 "No" → 該指令被擋下（agent 收到被拒理由，會改走別的路）。
 * - 選 "Allow all (this session)" → 本次 session 之後不再詢問（方便長段操作）。
 * - 非互動模式（無 UI）→ 一律擋下，安全優先。
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	// 特別危險的指令，即使選了 "Allow all" 仍會再次確認。
	const dangerousPatterns = [/\brm\s+(-rf?|--recursive)/i, /\bsudo\b/i, /\b(chmod|chown)\b.*777/i, /\bmkfs\b/i, /\bdd\s+if=/i];

	let allowAllThisSession = false;

	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash") return undefined;

		const command = (event.input.command as string) ?? "";
		const isDangerous = dangerousPatterns.some((p) => p.test(command));

		// 已授權整個 session，且非特別危險 → 放行。
		if (allowAllThisSession && !isDangerous) return undefined;

		// 非互動模式無法詢問 → 安全起見一律擋下。
		if (!ctx.hasUI) {
			return { block: true, reason: "Permission gate: no UI for confirmation, blocked by default." };
		}

		const label = isDangerous ? "⚠️ 危險指令，請確認" : "Agent 想執行 bash 指令";
		const options = isDangerous ? ["Yes", "No"] : ["Yes", "No", "Allow all (this session)"];
		const choice = await ctx.ui.select(`${label}：\n\n  ${command}\n\n是否允許？`, options);

		if (choice === "Allow all (this session)") {
			allowAllThisSession = true;
			return undefined;
		}
		if (choice !== "Yes") {
			return { block: true, reason: "Blocked by user." };
		}
		return undefined;
	});
}
