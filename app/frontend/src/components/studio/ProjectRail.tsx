import { Database, FolderOpen, LayoutGrid, Plus, Rocket, Settings, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProjectSummary } from '@/lib/studio';

interface ProjectRailProps {
  projects: ProjectSummary[];
  activeId: number | null;
  loading: boolean;
  busy: boolean;
  activeNav: 'studio' | 'deploy' | 'cloud' | 'settings';
  onSelect: (project: ProjectSummary) => void;
  onCreate: () => void;
  onDelete: (project: ProjectSummary) => void;
  onNavigate: (target: 'studio' | 'deploy' | 'cloud' | 'settings') => void;
}

const navItems = [
  { key: 'studio' as const, label: '工作台', icon: LayoutGrid },
  { key: 'deploy' as const, label: '部署与分享', icon: Rocket },
  { key: 'cloud' as const, label: 'Cloud 后端', icon: Database },
  { key: 'settings' as const, label: '设置', icon: Settings },
];

export function ProjectRail({
  projects,
  activeId,
  loading,
  busy,
  activeNav,
  onSelect,
  onCreate,
  onDelete,
  onNavigate,
}: ProjectRailProps) {
  return (
    <aside className="flex h-full w-full flex-col border-r border-line bg-canvas">
      <div className="flex h-14 items-center gap-2.5 px-4">
        <span className="flex h-6 w-6 items-center justify-center rounded-[5px] border-[1.5px] border-brand">
          <span className="h-2 w-2 rounded-[2px] bg-brand" />
        </span>
        <span className="text-[15px] font-semibold tracking-[-0.01em] text-ink">Atoms Studio</span>
      </div>

      <nav aria-label="主导航" className="px-2.5 pb-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeNav === item.key;
          return (
            <button
              key={item.key}
              type="button"
              disabled={busy}
              onClick={() => onNavigate(item.key)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex h-9 w-full items-center gap-2.5 rounded-md px-2.5 text-[13px] transition-colors',
                active
                  ? 'bg-brand-soft font-medium text-brand-ink'
                  : 'text-ink-soft hover:bg-white hover:text-ink'
              )}
            >
              <Icon className="h-[15px] w-[15px]" strokeWidth={1.75} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="flex items-center justify-between px-4 pb-2 pt-1">
        <span className="mono text-[10.5px] uppercase tracking-[0.09em] text-ink-faint">项目</span>
        <button
          type="button"
              disabled={busy}
          onClick={onCreate}
          aria-label="新建项目"
          className="flex h-6 w-6 items-center justify-center rounded text-ink-faint transition-colors hover:bg-white hover:text-ink"
        >
          <Plus className="h-[14px] w-[14px]" strokeWidth={2} />
        </button>
      </div>

      <div className="studio-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {loading ? (
          <div className="space-y-1.5 px-1 py-1">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-md bg-line/50" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <p className="px-2 py-3 text-[12.5px] leading-relaxed text-ink-faint">
            还没有项目。输入一句需求即可开始。
          </p>
        ) : (
          <ul className="space-y-0.5">
            {projects.map((project) => {
              const active = project.id === activeId;
              return (
                <li key={project.id} className="group relative">
                  <button
                    type="button"
              disabled={busy}
                    onClick={() => onSelect(project)}
                    aria-current={active ? 'true' : undefined}
                    className={cn(
                      'flex w-full items-start gap-2 rounded-md py-2 pl-2.5 pr-8 text-left transition-colors',
                      active ? 'bg-brand-soft' : 'hover:bg-white'
                    )}
                  >
                    <FolderOpen
                      className={cn(
                        'mt-0.5 h-[13px] w-[13px] shrink-0',
                        active ? 'text-brand' : 'text-ink-faint'
                      )}
                      strokeWidth={1.75}
                    />
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          'block truncate text-[13px] leading-5',
                          active ? 'font-medium text-brand-ink' : 'text-ink'
                        )}
                      >
                        {project.name}
                      </span>
                      <span className="mono block text-[10.5px] leading-4 text-ink-faint">
                        {project.version_count > 0
                          ? `v${project.current_version ?? project.version_count} · ${project.version_count} 个版本`
                          : '草稿'}
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
              disabled={busy}
                    onClick={() => onDelete(project)}
                    aria-label={`删除项目 ${project.name}`}
                    className="absolute right-1.5 top-2 flex h-6 w-6 items-center justify-center rounded text-ink-faint opacity-0 transition-opacity hover:bg-white hover:text-err focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 className="h-[13px] w-[13px]" strokeWidth={1.75} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-line p-3 text-xs text-ink-soft">共享数据 · 预置模拟输出</div>
    </aside>
  );
}
