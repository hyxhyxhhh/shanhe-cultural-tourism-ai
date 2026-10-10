import { AdminOnly } from "@/components/access/admin-only";
import { ClientsPage } from "@/components/common/overview-panels";
export default function Page(){ return <AdminOnly><ClientsPage/></AdminOnly>; }
