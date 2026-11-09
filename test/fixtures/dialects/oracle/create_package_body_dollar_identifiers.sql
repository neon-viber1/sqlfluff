CREATE OR REPLACE PACKAGE testpkg IS
    PROCEDURE foo( x IN NUMBER );
END testpkg;
/

CREATE OR REPLACE PACKAGE BODY testpkg IS
    PROCEDURE private$helper( x IN NUMBER ) IS
    BEGIN
        NULL;
    END private$helper;
END testpkg;
/

CREATE OR REPLACE PACKAGE dollar_identifiers IS
    PROCEDURE foo( p$id IN NUMBER );
END dollar_identifiers;
/

CREATE OR REPLACE PACKAGE BODY dollar_identifiers IS
    g_my$var NUMBER;
    TYPE r IS RECORD ( my$field NUMBER );

    FUNCTION private$function( p$id IN NUMBER ) RETURN NUMBER IS
        v_dollar$val NUMBER;
    BEGIN
        v_dollar$val := p$id + 1;
        RETURN v_dollar$val;
    END private$function;

    PROCEDURE private$helper( p$id IN NUMBER ) IS
        v_result NUMBER;
        v_record r;
    BEGIN
        v_result := p$id + 1;
        v_record.my$field := private$function(v_result);
        g_my$var := v_record.my$field;
    END private$helper;

    PROCEDURE foo( p$id IN NUMBER ) IS
    BEGIN
        private$helper(p$id);
    END foo;
END dollar_identifiers;
/

CREATE OR REPLACE PACKAGE spec_dollar_parameter IS
    PROCEDURE foo( p$id IN NUMBER );
END spec_dollar_parameter;
/

CREATE OR REPLACE PACKAGE BODY spec_dollar_parameter IS
    PROCEDURE foo( ordinary_id IN NUMBER ) IS
    BEGIN
        NULL;
    END foo;
END spec_dollar_parameter;
/
