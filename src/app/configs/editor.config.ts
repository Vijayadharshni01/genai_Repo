import { UserConfig } from 'monaco-editor-wrapper';

export const createEditorConfig = (code: string, language: 'csharp' | 'java', readOnly: boolean = true): UserConfig => {
    return {
        wrapperConfig: {
            editorAppConfig: {
                $type: 'classic',
                codeResources: {
                    main: {
                        text: code,
                        fileExt: language === 'csharp' ? 'cs' : 'java',
                    },
                },
                useDiffEditor: false,
                editorOptions: {
                    theme: 'vs-dark',
                    readOnly: readOnly,
                    minimap: { enabled: false },
                    automaticLayout: true,
                    scrollBeyondLastLine: false
                }
            },
        }
    };
};
