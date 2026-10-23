/**
 * 全局对象声明：本仓库的前端是"无模块系统"的原生 JS，
 * 各文件通过挂在 window 上的全局对象互相消费。
 *
 * 为什么需要这个文件：
 *   `tsc --checkJs` 默认不认识 `window.TmallUI` / `window.TmallRuntime` 这类
 *   自定义全局，会把每一处访问都报成 TS2339。本文件把这些全局登记一次，
 *   让类型检查能聚焦在真正的逻辑错误上（例如变量越作用域、对象字段拼写错误），
 *   而不是被 30 多处"属性不存在"淹没。
 *
 * 维护约定：新增跨文件全局时，在这里补一行声明。
 *   只写"消费方真正会用到"的成员，不追求与实现完全一致。
 */

/** Lucide 图标运行时（lucide-custom.min.js 提供）。 */
interface LucideRuntime {
  createIcons: (options?: { nodes?: Element[] }) => void;
}

/** 页面数据入口（api.js 提供）。 */
interface DemoApiRuntime {
  request: (url: string, options?: any) => Promise<any>;
  loadPageCapabilities?: (pageKey: string) => Promise<any>;
  renderDataState?: (container: Element, state: string, details?: any) => Element;
  [key: string]: any;
}

/** 字段选择器（field-selector.js 提供）。 */
interface DemoFieldSelectorRuntime {
  create: (options?: any) => any;
}

/** 日期范围状态仓（runtime/date-range-store.js 提供）。 */
interface TmallDateRangeState {
  startDate: string;
  endDate: string;
  preset: string;
  compareMode: string;
  dim: string;
  origin?: string;
}

interface TmallDateRangeRuntime {
  getState: () => TmallDateRangeState;
  subscribe: (subscriber: (state: TmallDateRangeState) => void, immediate?: boolean) => () => void;
  setRange: (start: string, end: string, preset?: string) => boolean;
  setReviewRange: (start: string, end: string) => boolean;
}

/** 跨页面共享的运行时工具（runtime/*.js 提供）。 */
interface TmallRuntimeNamespace {
  subscribeDateRange?: (handler: (state: any) => void, options?: { immediate?: boolean }) => () => void;
  getDateRange?: () => any;
  createDateRangeStore?: (deps: any) => TmallDateRangeRuntime;
  [key: string]: any;
}

/** 浮层原语句柄（TmallUI.popover 返回）。 */
interface TmallPopoverHandle {
  node: HTMLElement;
  panel: HTMLElement;
  reposition: () => void;
  close: (options?: { restoreFocus?: boolean }) => TmallPopoverHandle;
  destroy: () => TmallPopoverHandle;
  isOpen: () => boolean;
}

/** 组件层公开 API（ui-components.js 提供）。 */
interface TmallUIComponentApi {
  text: (node: Element | null, value: any) => Element | null;
  create: (tag: string, className?: string, value?: any) => HTMLElement;
  clear: (node: Element | null) => Element | null;
  escape: (value: any) => string;
  formatDateTime: (value: any) => string;
  format: { number: Function; money: Function; percent: Function; dateTime: Function };
  status: Function;
  renderDataState: (node: Element | null, state: string, details?: any) => Element | null;
  icon: (name: string, label?: string) => HTMLElement;
  button: (options?: any) => HTMLButtonElement;
  badge: (label: string, tone?: string) => HTMLElement;
  emptyState: (message?: string, detail?: string) => HTMLElement;
  dataState: (state?: string, details?: any) => HTMLElement;
  metricCard: (options?: any) => HTMLElement;
  metricGrid: (cards?: any[], className?: string) => HTMLElement;
  panel: (options?: any) => HTMLElement;
  pageHeader: (options?: any) => HTMLElement;
  filterToolbar: (content?: any, actions?: any) => HTMLElement;
  table: ((options?: {
    caption?: string; columns?: Array<{ key?: string; label?: string; numeric?: boolean; rowHeader?: boolean; scope?: string; className?: string; headerClassName?: string; render?: (value: any, row: any, rowIndex: number, columnIndex: number, footer: boolean) => any; renderHeader?: (column: any, index: number) => any }>;
    rows?: any[]; footerRows?: any[]; className?: string; tableClass?: string; wrapClass?: string; emptyMessage?: string; rowClassName?: string | ((row: any, rowIndex: number, footer: boolean) => string); renderRow?: (row: any, rowIndex: number) => HTMLTableRowElement; tableControls?: boolean;
  }) => HTMLElement) & {
    mount: (target: HTMLTableElement | HTMLTableSectionElement | string, options?: any) => HTMLTableElement | null;
  };
  productIdentity: (options?: {
    title?: string; id?: string; imageUrl?: string; showThumbnail?: boolean; showId?: boolean;
    maxTitleChars?: number; className?: string; titleClassName?: string;
    onTitleClick?: (() => void) | null; metaItems?: Element[]; metaText?: string;
  }) => HTMLElement;
  setState: (root: Element, state: string, details?: any) => void;
  contextBar: (options?: any) => HTMLElement;
  tableToolbar: (options?: any) => HTMLElement;
  detailDrawer: (options?: any) => any;
  stickyActionBar: (options?: any) => HTMLElement;
  modal: (options?: any) => any;
  confirm: (options?: any) => Promise<boolean>;
  popover: (options?: {
    anchor?: Element | null;
    content?: any;
    placement?: string;
    className?: string;
    matchAnchorWidth?: boolean;
    closeOnOutside?: boolean;
    onClose?: () => void;
  }) => TmallPopoverHandle;
  enableLightDismiss: (dialog: HTMLDialogElement) => HTMLDialogElement;
  fieldSelector: (options?: any) => any;
  audit: (root?: Element | Document) => any[];
}

// Only the public ECharts members consumed by the shared canvas-theme bridge.
interface EChartsThemeInstance {
  on: (event: 'rendered', handler: () => void) => void;
  isDisposed: () => boolean;
  getOption: () => any;
  setOption: (option: any, options?: { silent?: boolean }) => void;
}
interface EChartsThemeRuntime {
  registerPreprocessor?: (preprocessor: (option: any) => void) => void;
  getInstanceByDom: (node: Element) => EChartsThemeInstance | undefined;
}

interface Window {
  echarts?: EChartsThemeRuntime;
  lucide?: LucideRuntime;
  DemoApi?: DemoApiRuntime;
  DemoFieldSelector?: DemoFieldSelectorRuntime;
  TmallUI?: TmallUIComponentApi;
  TmallDateRange?: TmallDateRangeRuntime;
  TmallRuntime?: TmallRuntimeNamespace;
}
