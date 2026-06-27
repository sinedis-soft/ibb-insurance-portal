import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "IBB Insurance Portal",
  description: "IBB Insurance Portal MVP frontend",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
