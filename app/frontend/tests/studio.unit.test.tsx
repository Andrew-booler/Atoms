import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ArtifactPreview } from '../src/components/studio/ArtifactPreview';
import { ConversationStream } from '../src/components/studio/ConversationStream';
import { PlanCard } from '../src/components/studio/PlanCard';
import { PlaceholderPanel } from '../src/components/studio/PlaceholderPanel';
import { ProjectRail } from '../src/components/studio/ProjectRail';
import { RequirementComposer } from '../src/components/studio/RequirementComposer';
import { StudioOperation } from '../src/lib/studio-operation';
import type {
  ModelOption,
  PlanPayload,
  ProjectSummary,
  StudioMessage,
  VersionSummary,
} from '../src/lib/studio';

const project: ProjectSummary = {
  id: 101,
  name: '演示项目',
  current_version: 2,
  version_count: 2,
};
const draftProject: ProjectSummary = { id: 102, name: '草稿项目', version_count: 0 };
const plan: PlanPayload = {
  summary: '演示计划一',
  stack: ['HTML'],
  steps: [{ title: '显示演示', detail: '使用预置页面' }],
  files: [{ path: 'index.html', purpose: '固定预览' }],
};
const models: ModelOption[] = [{ key: 'balanced', model: 'mock-fixed-v1', label: '模拟', hint: '' }];
const html = '<html><body>固定中文</body></html>';

/** 与产品一致：外部动作统一由 onAction / onCopy 串行执行器包装 */
const runAction = async (action: () => Promise<void>) => {
  await action();
};

function railProps(overrides: Partial<ComponentProps<typeof ProjectRail>> = {}) {
  const base: ComponentProps<typeof ProjectRail> = {
    projects: [project],
    activeId: 101,
    loading: false,
    busy: false,
    activeNav: 'studio',
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    onDelete: vi.fn(),
    onNavigate: vi.fn(),
  };
  return { ...base, ...overrides } as ComponentProps<typeof ProjectRail>;
}

function previewProps(overrides: Partial<ComponentProps<typeof ArtifactPreview>> = {}) {
  const base: ComponentProps<typeof ArtifactPreview> = {
    html: null,
    title: '演示',
    busy: false,
    stageLabel: '',
    versions: [],
    activeVersion: null,
    onRestore: vi.fn(),
    restoring: false,
    onAction: runAction,
  };
  return { ...base, ...overrides } as ComponentProps<typeof ArtifactPreview>;
}

/** 受控输入外壳：让输入、快捷键、示例提示、配置切换都能真实触发 */
function ComposerHarness({
  onSubmit,
  onProfileChange,
  busy = false,
  disabled = false,
  suggestions = [],
  models: modelList = models,
  initialValue = '',
}: {
  onSubmit: () => void;
  onProfileChange?: (profile: string) => void;
  busy?: boolean;
  disabled?: boolean;
  suggestions?: string[];
  models?: ModelOption[];
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue);
  const [profile, setProfile] = useState(modelList[0]?.key ?? '');

  return (
    <RequirementComposer
      value={value}
      onChange={setValue}
      onSubmit={onSubmit}
      busy={busy}
      disabled={disabled}
      placeholder="需求"
      models={modelList}
      profile={profile}
      onProfileChange={(next) => {
        setProfile(next);
        onProfileChange?.(next);
      }}
      suggestions={suggestions}
    />
  );
}

const message = (overrides: Partial<StudioMessage> = {}): StudioMessage => ({
  id: 1,
  role: 'assistant',
  content: '消息',
  meta: {},
  created_at: 'invalid',
  ...overrides,
});

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    writable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe('导航', () => {
  it('导航-单元-01：主导航名称与无登录入口', async () => {
    const user = userEvent.setup();
    const props = railProps();
    render(<ProjectRail {...props} />);

    for (const name of ['工作台', '部署与分享', 'Cloud 后端']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.queryByText(/登录/)).toBeNull();
    expect(screen.getByRole('button', { name: '工作台' })).toHaveAttribute('aria-current', 'page');

    await user.click(screen.getByRole('button', { name: '部署与分享' }));
    expect(props.onNavigate).toHaveBeenCalledWith('deploy');
    expect(props.onNavigate).toHaveBeenCalledTimes(1);
  });

  it('导航-单元-02：占位页面与返回意图', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={['/deploy']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route
            path="/deploy"
            element={
              <PlaceholderPanel
                eyebrow="部署"
                title="部署"
                description="说明"
                planned={[{ title: '尚未开放', detail: '无业务写入' }]}
              />
            }
          />
          <Route path="/" element={<div>工作台首页</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('尚未构建')).toBeInTheDocument();
    expect(screen.getByText('尚未开放')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '返回工作台' }));
    expect(screen.getByText('工作台首页')).toBeInTheDocument();
  });

  it('导航-单元-03：执行中导航全部禁用', () => {
    const props = railProps({ busy: true });
    render(<ProjectRail {...props} />);

    for (const name of ['工作台', '部署与分享', 'Cloud 后端', '设置', '新建项目']) {
      expect(screen.getByRole('button', { name })).toBeDisabled();
    }
    expect(screen.getByRole('button', { name: '删除项目 演示项目' })).toBeDisabled();
    expect(screen.getByText('演示项目').closest('button')).toBeDisabled();

    // 七个可交互控件（4 导航 + 新建 + 项目 + 删除）全部禁用
    expect(screen.getAllByRole('button').filter((node) => node.hasAttribute('disabled'))).toHaveLength(
      7
    );
  });
});

describe('项目', () => {
  it('项目-单元-01：空项目页面', () => {
    render(<ProjectRail {...railProps({ projects: [] })} />);
    expect(screen.getByText(/还没有项目/)).toBeInTheDocument();
  });

  it('项目-单元-02：加载及列表摘要', async () => {
    const user = userEvent.setup();
    const loading = railProps({ loading: true });
    const view = render(<ProjectRail {...loading} />);
    expect(view.container.querySelectorAll('.animate-pulse')).toHaveLength(3);

    const props = railProps();
    view.rerender(<ProjectRail {...props} />);

    expect(screen.getByText('演示项目')).toBeInTheDocument();
    expect(screen.getByText('v2 · 2 个版本')).toBeInTheDocument();

    await user.click(screen.getByText('演示项目'));
    expect(props.onSelect).toHaveBeenCalledWith(project);
  });

  it('项目-单元-03：删除意图绑定名称且执行中禁用', async () => {
    const user = userEvent.setup();
    const busy = railProps({ busy: true });
    const view = render(<ProjectRail {...busy} />);

    const removeButton = screen.getByRole('button', { name: '删除项目 演示项目' });
    expect(removeButton).toBeDisabled();
    expect(busy.onDelete).not.toHaveBeenCalled();
    view.unmount();

    const idle = railProps({ projects: [project, draftProject] });
    render(<ProjectRail {...idle} />);
    expect(screen.getByText('草稿')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '删除项目 演示项目' }));
    expect(idle.onDelete).toHaveBeenCalledWith(project);
  });
});

describe('输入', () => {
  it('输入-单元-01：空白不可提交，有效输入可提交', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ComposerHarness onSubmit={onSubmit} initialValue="   " />);

    const submit = screen.getByRole('button', { name: '生成计划' });
    expect(submit).toBeDisabled();

    const box = screen.getByLabelText('描述你想要的应用');
    await user.click(box);
    await user.keyboard('{Control>}{Enter}{/Control}');
    expect(onSubmit).not.toHaveBeenCalled();

    await user.clear(box);
    await user.type(box, '记录饮水');
    expect(submit).toBeEnabled();

    await user.click(box);
    await user.keyboard('{Control>}{Enter}{/Control}');
    expect(onSubmit).toHaveBeenCalledTimes(1);

    await user.click(submit);
    expect(onSubmit).toHaveBeenCalledTimes(2);
  });

  it('输入-单元-02：四提示及执行中不可操作', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const busyView = render(
      <ComposerHarness
        onSubmit={onSubmit}
        busy
        disabled
        suggestions={['甲', '乙', '丙', '丁']}
      />
    );

    for (const item of ['甲', '乙', '丙', '丁']) {
      expect(screen.getByRole('button', { name: item })).toBeDisabled();
    }
    expect(screen.getByRole('button', { name: '生成中' })).toBeDisabled();
    expect(screen.getByLabelText('描述你想要的应用')).toBeDisabled();
    expect(screen.getByLabelText('输出配置')).toBeDisabled();
    busyView.unmount();

    render(<ComposerHarness onSubmit={onSubmit} suggestions={['记录饮水']} />);
    await user.click(screen.getByRole('button', { name: '记录饮水' }));
    expect(screen.getByLabelText('描述你想要的应用')).toHaveValue('记录饮水');
    expect(screen.getByRole('button', { name: '生成计划' })).toBeEnabled();
  });

  it('输入-单元-03：配置空态与多行emoji保留', async () => {
    const user = userEvent.setup();
    const onProfileChange = vi.fn();
    const emptyModels = render(<ComposerHarness onSubmit={vi.fn()} models={[]} initialValue={'中文\n😀'} />);

    expect(screen.getByLabelText('输出配置')).toBeDisabled();
    expect(screen.getByLabelText('描述你想要的应用')).toHaveValue('中文\n😀');
    emptyModels.unmount();

    const twoModels: ModelOption[] = [
      ...models,
      { key: 'quality', model: 'mock-fixed-v2', label: '精细', hint: '' },
    ];
    render(
      <ComposerHarness
        onSubmit={vi.fn()}
        models={twoModels}
        initialValue={'中文\n😀'}
        onProfileChange={onProfileChange}
      />
    );
    expect(screen.getByLabelText('描述你想要的应用')).toHaveValue('中文\n😀');
    await user.selectOptions(screen.getByLabelText('输出配置'), 'quality');
    expect(onProfileChange).toHaveBeenCalledWith('quality');
  });
});

describe('计划', () => {
  it('计划-单元-01：计划字段及确认状态', async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const view = render(
      <PlanCard
        plan={plan}
        state="pending"
        onApprove={onApprove}
        onRevise={vi.fn()}
        onCopy={runAction}
      />
    );

    for (const text of ['演示计划一', '显示演示', '使用预置页面', 'index.html', '固定预览']) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByText('待确认')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '确认执行' }));
    expect(onApprove).toHaveBeenCalledTimes(1);

    view.rerender(<PlanCard plan={plan} state="done" onCopy={runAction} />);
    expect(screen.queryByText('确认执行')).toBeNull();
    expect(screen.getByText('已执行')).toBeInTheDocument();
  });

  it('计划-单元-02：调整按钮禁用不发调用', async () => {
    const user = userEvent.setup();
    const onRevise = vi.fn();
    const onApprove = vi.fn();
    render(
      <PlanCard
        plan={plan}
        state="pending"
        approveDisabled
        onApprove={onApprove}
        onRevise={onRevise}
        onCopy={runAction}
      />
    );

    expect(screen.getByRole('button', { name: '确认执行' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '调整需求' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '复制计划' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: '调整需求' }));
    await user.click(screen.getByRole('button', { name: '确认执行' }));
    expect(onRevise).not.toHaveBeenCalled();
    expect(onApprove).not.toHaveBeenCalled();
  });

  it('计划-单元-03：复制按钮与成功前无假提示', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      writable: true,
      value: { writeText },
    });
    const onCopy = vi.fn(runAction);

    const view = render(<PlanCard plan={plan} state="pending" onCopy={onCopy} />);
    expect(screen.queryByText('已复制')).toBeNull();

    await user.click(screen.getByRole('button', { name: '复制计划' }));
    await waitFor(() => expect(screen.getByText('已复制')).toBeInTheDocument());

    expect(onCopy).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain('演示计划一');
    expect(copied).toContain('1. 显示演示 — 使用预置页面');
    expect(copied).toContain('index.html — 固定预览');
    view.unmount();

    // 剪贴板拒绝时不得出现“已复制”，错误交回串行执行器
    const errors: string[] = [];
    const failingClipboard = vi.fn().mockRejectedValue(new Error('denied'));
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      writable: true,
      value: { writeText: failingClipboard },
    });
    render(
      <PlanCard
        plan={plan}
        state="pending"
        onCopy={async (action) => {
          try {
            await action();
          } catch (error) {
            errors.push((error as Error).message);
          }
        }}
      />
    );
    await user.click(screen.getByRole('button', { name: '复制计划' }));
    await waitFor(() => expect(errors.length).toBe(1));
    expect(errors[0]).toContain('复制计划失败');
    expect(screen.queryByText('已复制')).toBeNull();
  });
});

describe('构建', () => {
  it('构建-单元-01：串行阶段与禁止第二动作', async () => {
    let finish!: () => void;
    const busy: boolean[] = [];
    const calls: string[] = [];
    const operation = new StudioOperation(
      (value) => busy.push(value),
      () => {},
      String
    );

    const first = operation.run(async () => {
      calls.push('结构');
      await new Promise<void>((resolve) => {
        finish = resolve;
      });
      calls.push('产物');
    });
    await operation.run(async () => {
      calls.push('第二动作');
    });

    expect(calls).toEqual(['结构']);
    expect(operation.busy).toBe(true);

    finish();
    await first;
    expect(calls).toEqual(['结构', '产物']);
    expect(busy).toEqual([true, false]);
    expect(operation.canRetry).toBe(false);
  });

  it('构建-单元-02：失败释放与重试真实调用', async () => {
    let count = 0;
    const errors: (string | null)[] = [];
    const operation = new StudioOperation(
      () => {},
      (value) => errors.push(value),
      String
    );

    await operation.run(async () => {
      if (++count === 1) throw new Error('失败');
    });
    expect(operation.busy).toBe(false);
    expect(operation.canRetry).toBe(true);

    await operation.retry();
    expect(count).toBe(2);
    expect(operation.canRetry).toBe(false);
    expect(errors.some((item) => item?.includes('失败'))).toBe(true);
  });

  it('构建-单元-03：消息错误与无效时间', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ConversationStream
        messages={[message()]}
        planState="pending"
        onApprove={vi.fn()}
        onRevise={vi.fn()}
        onCopy={runAction}
        onRetry={onRetry}
        busy={false}
        error="保存失败"
      />
    );

    expect(screen.getByText('消息')).toBeInTheDocument();
    expect(screen.queryByText('NaN')).toBeNull();
    expect(screen.getByRole('alert')).toHaveTextContent('保存失败');

    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('预览', () => {
  it('预览-单元-01：空态及两种宽度', async () => {
    const user = userEvent.setup();
    const props = previewProps({ html });
    const view = render(<ArtifactPreview {...props} />);

    expect(screen.getByRole('button', { name: '桌面视图' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: '移动视图' }));
    expect(screen.getByRole('button', { name: '移动视图' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTitle('演示 预览').parentElement?.className).toContain('max-w-[390px]');

    await user.click(screen.getByRole('button', { name: '桌面视图' }));
    expect(screen.getByRole('button', { name: '桌面视图' })).toHaveAttribute('aria-pressed', 'true');

    view.rerender(<ArtifactPreview {...previewProps()} />);
    expect(screen.getByText('预览区还是空的')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新加载预览' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '在新标签页打开' })).toBeDisabled();
    view.unmount();
  });

  it('预览-单元-02：执行中禁止刷新与外开', async () => {
    const user = userEvent.setup();
    const errors: string[] = [];
    const createObjectURL = vi.fn(() => 'blob:mock-url');
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: revokeObjectURL,
    });
    const openSpy = vi.spyOn(window, 'open').mockReturnValue({ opener: null } as unknown as Window);

    const busyView = render(
      <ArtifactPreview {...previewProps({ html, busy: true, stageLabel: '正在构建产物' })} />
    );
    expect(screen.getByRole('button', { name: '重新加载预览' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '在新标签页打开' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '移动视图' })).toBeDisabled();
    expect(screen.getByText('正在构建产物')).toBeInTheDocument();

    const frame = screen.getByTitle('演示 预览');
    expect(frame).toHaveAttribute('tabindex', '-1');
    expect(frame.className).toContain('pointer-events-none');
    busyView.unmount();

    render(
      <ArtifactPreview
        {...previewProps({
          html,
          onAction: async (action) => {
            try {
              await action();
            } catch (error) {
              errors.push((error as Error).message);
            }
          },
        })}
      />
    );
    await user.click(screen.getByRole('button', { name: '在新标签页打开' }));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(openSpy).toHaveBeenCalledWith('blob:mock-url', '_blank');
    expect(errors).toHaveLength(0);

    openSpy.mockReturnValue(null as unknown as Window);
    await user.click(screen.getByRole('button', { name: '在新标签页打开' }));
    expect(errors[0]).toContain('外开页面被浏览器阻止');
  });

  it('预览-单元-03：iframe传入完整文档与沙箱', async () => {
    const user = userEvent.setup();
    render(<ArtifactPreview {...previewProps({ html })} />);

    const frame = screen.getByTitle('演示 预览');
    expect(frame).toHaveAttribute('srcdoc', html);
    expect(frame).toHaveAttribute('sandbox', 'allow-scripts allow-forms allow-modals allow-popups');
    expect(screen.getByText(/\/preview · 演示/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '重新加载预览' }));
    expect(screen.getByTitle('演示 预览')).toBeInTheDocument();
  });
});

describe('版本', () => {
  const versions: VersionSummary[] = [
    { id: 202, version_no: 2 },
    { id: 201, version_no: 1 },
  ];

  it('版本-单元-01：序号与记录id分离', () => {
    render(<ArtifactPreview {...previewProps({ html, activeVersion: 1, versions })} />);

    const select = screen.getByLabelText('选择版本') as HTMLSelectElement;
    expect(select).toHaveValue('1');
    expect(select.options).toHaveLength(2);
    expect(select.options[0].text).toContain('v2');
    expect(select.options[1].text).toContain('v1 · 当前');
    expect(select.textContent).not.toContain('v201');
  });

  it('版本-单元-02：无版本不显示选择器及执行中禁用', async () => {
    const user = userEvent.setup();
    const empty = render(<ArtifactPreview {...previewProps({ html })} />);
    expect(screen.queryByLabelText('选择版本')).toBeNull();
    empty.unmount();

    const onRestore = vi.fn();
    const view = render(
      <ArtifactPreview {...previewProps({ html, busy: true, versions, onRestore })} />
    );
    expect(screen.getByLabelText('选择版本')).toBeDisabled();
    view.rerender(<ArtifactPreview {...previewProps({ html, versions, onRestore })} />);

    await user.selectOptions(screen.getByLabelText('选择版本'), '2');
    expect(onRestore).toHaveBeenCalledWith(versions[0]);
  });

  it('版本-单元-03：部分成功读取重试不重复恢复替身', async () => {
    let restored = false;
    let writes = 0;
    let reads = 0;
    const operation = new StudioOperation(
      () => {},
      () => {},
      String
    );

    await operation.run(async () => {
      if (!restored) {
        writes++;
        restored = true;
      }
      if (++reads === 1) throw new Error('读取失败');
    });
    await operation.retry();

    expect(writes).toBe(1);
    expect(reads).toBe(2);
  });
});
