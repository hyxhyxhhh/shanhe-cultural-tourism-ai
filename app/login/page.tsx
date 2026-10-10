import { LoginScreen } from "@/components/access/login-screen";
import { resolveLoginReturnTo } from "@/lib/platform/login-return";

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{ returnTo?: string | string[] }>;
}) {
  const { returnTo } = await searchParams;

  return (
    <LoginScreen
      backgroundVideo={process.env.NEXT_PUBLIC_LOGIN_BACKGROUND_VIDEO ?? "/videos/login-background.mp4"}
      returnTo={resolveLoginReturnTo(returnTo)}
    />
  );
}
