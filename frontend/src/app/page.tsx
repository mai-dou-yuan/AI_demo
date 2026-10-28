import AuthGate from '@/components/auth-gate';
export const dynamic = 'force-dynamic';
export default function Home() { return <AuthGate />; }
