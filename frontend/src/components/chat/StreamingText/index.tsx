'use client';

import ReactMarkdown from 'react-markdown';
import styles from './styles.module.css';

interface StreamingTextProps {
    content: string;
    isStreaming: boolean;
}

export default function StreamingText({ content, isStreaming }: StreamingTextProps) {
    return (
        <div className={styles.wrapper}>
            {isStreaming ? (
                <>
                    {content}
                    <span className={styles.cursor} />
                </>
            ) : (
                <ReactMarkdown>{content}</ReactMarkdown>
            )}
        </div>
    );
}
