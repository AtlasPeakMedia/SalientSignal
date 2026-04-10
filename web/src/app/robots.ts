import type { MetadataRoute } from "next";

/**
 * Block every crawler from every path while we're pre-launch.
 * After JAG/ethics review and public launch, loosen this to
 * allow specific paths.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        disallow: "/",
      },
    ],
  };
}
