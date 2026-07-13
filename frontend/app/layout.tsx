import type { Metadata, Viewport } from "next";
import { PwaRegister } from "./pwa-register";
import "./styles.css";

export const metadata: Metadata = {
  title: "IBB Insurance Portal",
  description: "IBB Insurance Portal MVP frontend",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "IBB Portal",
  },
  icons: {
    icon: [{ url: "/icons/pwa-icon-192.svg", sizes: "192x192", type: "image/svg+xml" }],
    apple: [{ url: "/icons/pwa-icon-192.svg", sizes: "192x192", type: "image/svg+xml" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2F6F8F",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>
        <PwaRegister />
        {children}
      </body>
    </html>
  );
}
