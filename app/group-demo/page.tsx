import { AdminOnly } from "@/components/access/admin-only";
import { GroupDemoPage } from "@/components/common/overview-panels";
export default function Page(){ return <AdminOnly><GroupDemoPage/></AdminOnly>; }
