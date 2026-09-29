import type { ReplayBundleV1 } from "../../replay/replay-v1-contract.d.ts";
import {
  ReplayCompatibilityError,
  validateReplayV1,
} from "../../replay/replay-v1-contract.mjs";

export class ReplayLoadError extends Error {
  readonly kind: "network" | "decode" | "compatibility";

  constructor(
    kind: ReplayLoadError["kind"],
    message: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ReplayLoadError";
    this.kind = kind;
  }
}

async function decodeResponse(response: Response): Promise<Uint8Array> {
  const payload = new Uint8Array(await response.arrayBuffer());
  const isGzip = payload[0] === 0x1f && payload[1] === 0x8b;
  if (!isGzip) return payload;

  if (typeof DecompressionStream === "undefined") {
    throw new ReplayLoadError(
      "decode",
      "This browser cannot decompress the published replay. Use the static summary instead.",
    );
  }

  try {
    const stream = new Blob([payload as BlobPart])
      .stream()
      .pipeThrough(new DecompressionStream("gzip"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  } catch (error) {
    throw new ReplayLoadError(
      "decode",
      "The replay could not be decompressed.",
      { cause: error },
    );
  }
}

export async function loadReplay(
  source: string,
  options: { signal?: AbortSignal; fetcher?: typeof fetch } = {},
): Promise<ReplayBundleV1> {
  const fetcher = options.fetcher ?? fetch;
  let response: Response;
  try {
    const init: RequestInit = {
      headers: { Accept: "application/json, application/gzip" },
    };
    if (options.signal !== undefined) init.signal = options.signal;
    response = await fetcher(source, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ReplayLoadError("network", "The replay could not be reached.", {
      cause: error,
    });
  }

  if (!response.ok) {
    throw new ReplayLoadError(
      "network",
      `The replay request failed with status ${response.status}.`,
    );
  }

  const decoded = await decodeResponse(response);
  let candidate: unknown;
  try {
    candidate = JSON.parse(new TextDecoder().decode(decoded));
  } catch (error) {
    throw new ReplayLoadError("decode", "The replay is not valid JSON.", {
      cause: error,
    });
  }

  try {
    return validateReplayV1(candidate, decoded.byteLength);
  } catch (error) {
    if (error instanceof ReplayCompatibilityError) {
      throw new ReplayLoadError("compatibility", error.message, {
        cause: error,
      });
    }
    throw error;
  }
}
