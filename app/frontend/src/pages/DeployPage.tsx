import { PlaceholderPanel } from '@/components/studio/PlaceholderPanel';

export default function DeployPage() {
  return (
    <PlaceholderPanel
      eyebrow="部署与分享"
      title="部署与分享"
      description="把工作台里生成的成品发布成可访问的链接，并控制谁能打开它。"
      planned={[
        {
          title: '一键发布为独立站点',
          detail: '为选中的版本生成稳定 URL，产物与预览使用同一份 HTML。',
        },
        {
          title: '访问权限',
          detail: '公开、仅团队成员、仅自己三档，可随时切换。',
        },
        {
          title: '分享卡片与嵌入',
          detail: '生成带封面的分享链接，以及可嵌入外站的 iframe 片段。',
        },
        {
          title: '发布记录',
          detail: '按版本记录发布时间与访问量，支持回滚到历史发布。',
        },
      ]}
    />
  );
}
