import { PlaceholderPanel } from '@/components/studio/PlaceholderPanel';

export default function CloudPage() {
  return <PlaceholderPanel eyebrow="Cloud 后端" title="Cloud 后端说明" description="工作台已经使用共享项目、消息和历史版本数据。本页仅为占位说明，不提供数据管理、认证或配置操作。" planned={[
    { title: '共享业务数据', detail: '所有使用者查看同一份工作台记录，不提供账号管理。' },
    { title: '项目与历史版本', detail: '返回工作台可提交需求、保存模拟网页并恢复历史。' },
    { title: '占位边界', detail: '本页没有增删改查、文件上传、服务配置或发布功能。' },
  ]} />;
}
