import type { Metadata } from "next";
import "./global.css";

export const metadata: Metadata = {
  title: "Nexus AI",
  description: "Plataforma de análise de mercado"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
