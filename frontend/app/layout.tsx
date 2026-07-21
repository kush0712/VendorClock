import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "VendorClock — MSE Compliance & Cash Priority",
  description:
    "Buyer-side compliance and cash-priority tool for Section 43B(h) / Section 37(2)(g), Income Tax Act 2025. Track MSE invoice deadlines, optimize payment priority, and generate audit exports.",
  keywords: ["43B(h)", "37(2)(g)", "MSE compliance", "MSME", "Form 3CD", "MSME-1", "vendor payments"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <QueryProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
