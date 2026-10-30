import { PlaceholderPanel } from '@/components/studio/PlaceholderPanel';

export default function CloudPage() {
  return (
    <PlaceholderPanel
      eyebrow="Cloud 后端"
      title="Cloud 后端能力"
      description="为生成的应用按需开通数据库、登录、文件存储与边缘函数，让原型直接长成可上线的产品。"
      planned={[
        {
          title: '数据表管理',
          detail: '在界面里定义实体字段，自动生成数据表与增删改查接口。',
        },
        {
          title: '用户与权限',
          detail: '复用平台登录体系，为生成的应用配置角色与数据可见范围。',
        },
        {
          title: '文件存储',
          detail: '上传头像、图片与附件，返回可直接渲染的持久访问地址。',
        },
        {
          title: '边缘函数',
          detail: '为需要服务端逻辑的流程编写接口，密钥只保存在服务端。',
        },
      ]}
    />
  );
}
